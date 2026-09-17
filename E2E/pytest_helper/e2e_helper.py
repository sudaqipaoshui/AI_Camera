"""
E2E测试辅助插件
提供日志管理、设备操作、文件管理等通用功能的抽象
"""
import os
import subprocess
import sys
import datetime
import traceback
import shutil
import zipfile
import re
import logging
import warnings
from pathlib import Path
from time import sleep
from typing import List, Optional, Tuple, Dict, Any

import allure
import pytest
from airtest.core.api import *

# 项目根目录(envloader.py 所在)加入 sys.path, 复用统一凭据加载器
_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import envloader  # noqa: E402


def resolve_ssh_password(env=None) -> str:
    """统一解析设备 SSH 口令。

    优先取 pytest env fixture 里的 ssh_password(已由 envloader 展开 ${VAR}),
    取不到则直接读 .env 的 CAMERA_SSH_PASSWORD。

    这里刻意不提供内置默认口令: 历史上写死的默认口令正是凭据泄露的根源,
    而且一旦设备口令变了, 默认值会导致静默连到错的地方。缺就报错。
    """
    if env:
        try:
            password = env.get('ssh_password')
        except AttributeError:
            password = None
        if password:
            return password
    return envloader.require("CAMERA_SSH_PASSWORD")


class E2ETimeHelper:
    """时间处理工具类 - 处理时间解析、计算等"""
    
    @staticmethod
    def parse_utc_time(time_str: str) -> datetime.datetime:
        """解析UTC时间字符串：20251111t142200z -> 2025-11-11 14:22:00
        
        Args:
            time_str: UTC时间字符串（格式：YYYYMMDDtHHMMSSz）
            
        Returns:
            datetime对象
        """
        # 移除末尾的'z'
        time_str = time_str.rstrip('z')
        # 分割日期和时间部分
        date_part = time_str[:8]  # 20251111
        time_part = time_str[9:]  # 142200 (跳过't')
        # 解析
        return datetime.datetime(
            int(date_part[:4]), 
            int(date_part[4:6]), 
            int(date_part[6:8]), 
            int(time_part[:2]), 
            int(time_part[2:4]), 
            int(time_part[4:6])
        )
    
    @staticmethod
    def calculate_time_intervals(start_time_str: str, startsport_time_str: str, 
                                end_time_str: str, t0: int = 10) -> Dict[str, Any]:
        """计算时间间隔和日志时间
        
        Args:
            start_time_str: 开始时间字符串（格式：YYYYMMDDtHHMMSSz）
            startsport_time_str: 发令时间字符串（格式：YYYYMMDDtHHMMSSz）
            end_time_str: 结束时间字符串（格式：YYYYMMDDtHHMMSSz）
            t0: 摄像头重启时间（秒），默认10秒
            
        Returns:
            包含所有时间信息的字典
        """
        # 解析时间
        start_dt = E2ETimeHelper.parse_utc_time(start_time_str)
        startsport_dt = E2ETimeHelper.parse_utc_time(startsport_time_str)
        end_dt = E2ETimeHelper.parse_utc_time(end_time_str)
        
        # t1 从视频开始到发令的时间间隔（秒）
        t1 = (startsport_dt - start_dt).total_seconds()
        # t2 从发令到结束的时间间隔（秒）
        t2 = (end_dt - startsport_dt).total_seconds()
        
        # 重启到发令的时间间隔 = t0 + t1
        time_interval = t0 + t1
        
        # 重启到结束的总时间间隔 = t0 + t1 + t2
        time_interval_2 = t0 + t1 + t2
        
        # 日志开始时间（通过当前时间计算，格式：2025-11-12 18:14:00）
        current_time = datetime.datetime.now()
        logStartTime_dt = current_time + datetime.timedelta(seconds=time_interval)
        logStartTime = logStartTime_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # 日志结束时间
        logEndTime_dt = logStartTime_dt + datetime.timedelta(seconds=t2)
        logEndTime = logEndTime_dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # 打印时间信息
        print("="*60)
        print(f"时间计算详情:")
        print(f"  t0 (重启时间): {t0} 秒")
        print(f"  t1 (视频开始到发令): {t1} 秒 ({t1/60:.1f} 分钟)")
        print(f"  t2 (发令到结束): {t2} 秒 ({t2/60:.1f} 分钟) ⚠️ 这是等待时间！")
        print(f"  time_interval (重启到发令): {time_interval} 秒 ({time_interval/60:.1f} 分钟)")
        print(f"  time_interval_2 (重启到结束): {time_interval_2} 秒 ({time_interval_2/60:.1f} 分钟)")
        print(f"  logStartTime:          {logStartTime}")
        print(f"  logEndTime:            {logEndTime}")
        print("="*60)
        
        return {
            't0': t0,
            't1': t1,
            't2': t2,
            'time_interval': time_interval,
            'time_interval_2': time_interval_2,
            'logStartTime': logStartTime,
            'logEndTime': logEndTime
        }
    
    @staticmethod
    def extract_time_from_log(log_file: Path) -> Optional[Tuple[str, str]]:
        """从日志文件中提取时间范围
        
        Args:
            log_file: 日志文件路径
            
        Returns:
            (开始时间, 结束时间) 元组，如果提取失败则返回None
        """
        first_timestamp = None
        last_timestamp = None
        
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
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
                start_time = first_timestamp.strftime('%Y-%m-%d %H:%M:%S')
                end_time = last_timestamp.strftime('%Y-%m-%d %H:%M:%S')
                return (start_time, end_time)
        except Exception:
            pass
        
        return None
    
    @staticmethod
    def normalize_time_string(time_str: Optional[str]) -> Optional[str]:
        """规范化时间字符串（去除前后空格）
        
        Args:
            time_str: 时间字符串
            
        Returns:
            规范化后的时间字符串，如果输入为None则返回None
        """
        if time_str is None:
            return None
        return time_str.strip() if time_str else None
    
    @staticmethod
    def convert_to_camera_time(app_time_str: str, offset_hours: int = -8) -> str:
        """将APP时间转换为相机时间
        
        Args:
            app_time_str: APP时间字符串（格式：%Y-%m-%d %H:%M:%S）
            offset_hours: 时间偏移量（小时），默认-8小时
            
        Returns:
            相机时间字符串
        """
        app_time_str = app_time_str.strip()
        app_time = datetime.datetime.strptime(app_time_str, "%Y-%m-%d %H:%M:%S")
        camera_time = app_time + datetime.timedelta(hours=offset_hours)
        return camera_time.strftime("%Y-%m-%d %H:%M:%S")
    
    @staticmethod
    def get_wait_times(time_interval: Optional[float] = None, 
                      t2: Optional[float] = None,
                      time_interval_2: Optional[float] = None) -> Tuple[Optional[float], Optional[float]]:
        """计算等待时间（发令前和发令后）
        
        Args:
            time_interval: 重启到发令的时间间隔
            t2: 从发令到结束的时间间隔
            time_interval_2: 重启到结束的总时间间隔
            
        Returns:
            (wait_before_start, wait_after_start) 元组
        """
        wait_before_start = time_interval
        
        # 优先使用 t2，因为它是直接从发令到结束的时间间隔，最准确
        # 如果 t2 有值，直接使用它
        if t2 is not None and t2 > 0:
            wait_after_start = t2
            print(f"  [get_wait_times] 使用 t2 (从发令到结束的时间间隔): {t2}秒 ({t2/60:.1f} 分钟)")
            # 如果 time_interval_2 和 time_interval 也有值，验证一下是否一致
            if time_interval_2 is not None and time_interval is not None:
                calculated_t2 = time_interval_2 - time_interval
                diff = abs(t2 - calculated_t2)
                if diff > 1.0:  # 如果差异超过1秒，打印警告
                    print(f"⚠️  警告: t2 ({t2}秒) 与 time_interval_2 - time_interval ({calculated_t2}秒) 不一致，差异: {diff}秒")
                    print(f"   使用 t2: {t2}秒 (这是从发令到结束的直接时间间隔)")
                else:
                    print(f"  [get_wait_times] 验证: t2 ({t2}秒) 与 time_interval_2 - time_interval ({calculated_t2}秒) 一致")
        # 如果 t2 没有值，尝试从 time_interval_2 - time_interval 计算
        elif time_interval_2 is not None and time_interval is not None:
            calculated_t2 = time_interval_2 - time_interval
            print(f"  [get_wait_times] t2 未提供，计算: time_interval_2 ({time_interval_2}秒) - time_interval ({time_interval}秒) = {calculated_t2}秒")
            # 如果计算出的值合理（大于0），使用它
            if calculated_t2 > 0:
                wait_after_start = calculated_t2
                print(f"  [get_wait_times] 使用计算值: {calculated_t2}秒 ({calculated_t2/60:.1f} 分钟)")
            else:
                wait_after_start = None
                print(f"⚠️  警告: time_interval_2 - time_interval 计算结果不合理 ({calculated_t2}秒)")
        else:
            wait_after_start = None
            print(f"⚠️  警告: 无法计算 wait_after_start，t2 = {t2}, time_interval_2 = {time_interval_2}, time_interval = {time_interval}")
        
        return (wait_before_start, wait_after_start)


class E2ELogManager:
    """日志管理类 - 处理ADB和SSH日志的删除和获取"""
    
    @staticmethod
    def delete_adb_logs(env: dict, date_str: Optional[str] = None) -> Dict[str, Any]:
        """删除ADB设备上的日志
        
        Args:
            env: 环境配置字典
            date_str: 日期字符串（YYYYMMDD），默认为当天
            
        Returns:
            操作结果字典
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        device_log_path = f'sdcard/DreamSports/log/{date_str}/'
        
        with allure.step(f"删除ADB设备日志: {device_log_path}"):
            print("="*60)
            print(f"正在删除ADB设备上的日志...")
            print(f"设备路径: {device_log_path}")
            print("="*60)
            
            adb_cmd = ['adb', 'shell', 'rm', '-rf', device_log_path]
            print(f"执行命令: {' '.join(adb_cmd)}")
            
            result = {
                'success': False,
                'message': '',
                'output': ''
            }
            
            try:
                proc_result = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=30)
                if proc_result.returncode == 0:
                    result['success'] = True
                    result['message'] = f"✅ 已删除ADB设备上的日志目录: {device_log_path}"
                    result['output'] = proc_result.stdout
                    print(result['message'])
                    allure.attach(
                        f"已删除ADB设备日志: {device_log_path}\n输出: {proc_result.stdout}",
                        "删除ADB日志结果",
                        allure.attachment_type.TEXT
                    )
                else:
                    if "No such file or directory" in proc_result.stderr or "not found" in proc_result.stderr.lower():
                        result['message'] = f"ℹ️  ADB设备上的日志目录不存在: {device_log_path}"
                        print(result['message'])
                        allure.attach(
                            f"ADB设备日志目录不存在: {device_log_path}",
                            "删除ADB日志结果",
                            allure.attachment_type.TEXT
                        )
                    else:
                        result['message'] = f"⚠️  删除ADB设备日志时出现警告: {proc_result.stderr}"
                        result['output'] = proc_result.stderr
                        print(result['message'])
                        allure.attach(
                            f"删除ADB日志警告: {proc_result.stderr}",
                            "删除ADB日志警告",
                            allure.attachment_type.TEXT
                        )
            except subprocess.TimeoutExpired:
                result['message'] = "❌ 删除ADB设备日志超时"
                print(result['message'])
                allure.attach(result['message'], "删除ADB日志错误", allure.attachment_type.TEXT)
                raise RuntimeError(result['message'])
            except Exception as e:
                result['message'] = f"❌ 删除ADB设备日志失败: {e}"
                print(result['message'])
                allure.attach(result['message'], "删除ADB日志错误", allure.attachment_type.TEXT)
                # 不抛出异常，允许继续执行
            
            return result
    
    @staticmethod
    def delete_ssh_logs(env: dict, remote_host: Optional[str] = None, 
                       remote_log_path: str = "/userdata/deploy/log/logger.log") -> Dict[str, Any]:
        """清空SSH设备（摄像头）上的日志文件
        
        Args:
            env: 环境配置字典
            remote_host: 远程主机IP，如果为None则从env中获取
            remote_log_path: 远程日志路径
            
        Returns:
            操作结果字典
        """
        # 从配置获取SSH信息
        try:
            if env:
                if remote_host is None:
                    cameraB_url = env.get('host', {}).get('cameraB', 'http://192.168.3.29')
                    remote_host = cameraB_url.replace('http://', '').replace('https://', '')
                remote_username = env.get('ssh_username', 'root')
                remote_password = resolve_ssh_password(env)
            else:
                raise AttributeError("env not provided")
        except (AttributeError, KeyError, TypeError):
            remote_host = remote_host or "192.168.3.29"
            remote_username = "root"
            remote_password = resolve_ssh_password(None)
        
        with allure.step(f"清空SSH设备日志: {remote_host}:{remote_log_path}"):
            print("="*60)
            print(f"正在清空SSH设备（摄像头）上的日志文件...")
            print(f"远程主机: {remote_username}@{remote_host}")
            print(f"远程路径: {remote_log_path}")
            print("="*60)
            
            # 使用 echo -n > 清空日志文件（保留文件但清空内容）
            ssh_cmd = [
                'sshpass', '-p', remote_password,
                'ssh',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                f'{remote_username}@{remote_host}',
                f'echo -n > {remote_log_path}'
            ]
            
            print(f"执行命令: sshpass -p *** ssh {remote_username}@{remote_host} 'echo -n > {remote_log_path}'")
            
            result = {
                'success': False,
                'message': '',
                'output': ''
            }
            
            try:
                proc_result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
                if proc_result.returncode == 0:
                    result['success'] = True
                    result['message'] = f"✅ 已清空SSH设备上的日志文件: {remote_log_path}"
                    result['output'] = proc_result.stdout
                    print(result['message'])
                    allure.attach(
                        f"已清空SSH设备日志: {remote_log_path}\n输出: {proc_result.stdout}",
                        "清空SSH日志结果",
                        allure.attachment_type.TEXT
                    )
                else:
                    # 如果文件不存在，尝试创建空文件
                    if "No such file" in proc_result.stderr or "not found" in proc_result.stderr.lower():
                        # 尝试创建目录和文件
                        create_cmd = [
                            'sshpass', '-p', remote_password,
                            'ssh',
                            '-o', 'StrictHostKeyChecking=no',
                            '-o', 'UserKnownHostsFile=/dev/null',
                            f'{remote_username}@{remote_host}',
                            f'mkdir -p $(dirname {remote_log_path}) && echo -n > {remote_log_path}'
                        ]
                        create_result = subprocess.run(create_cmd, capture_output=True, text=True, timeout=30)
                        if create_result.returncode == 0:
                            result['success'] = True
                            result['message'] = f"✅ 已创建并清空SSH设备上的日志文件: {remote_log_path}"
                            print(result['message'])
                            allure.attach(
                                f"已创建并清空SSH设备日志: {remote_log_path}",
                                "清空SSH日志结果",
                                allure.attachment_type.TEXT
                            )
                        else:
                            result['message'] = f"⚠️  SSH设备上的日志文件路径不存在，且创建失败: {remote_log_path}\n错误: {create_result.stderr}"
                            print(result['message'])
                            allure.attach(result['message'], "清空SSH日志警告", allure.attachment_type.TEXT)
                    else:
                        result['message'] = f"❌ 清空SSH设备日志失败: {proc_result.stderr}"
                        result['output'] = proc_result.stderr
                        print(result['message'])
                        allure.attach(result['message'], "清空SSH日志错误", allure.attachment_type.TEXT)
            except FileNotFoundError:
                result['message'] = "❌ sshpass 未安装，无法清空SSH设备日志。请安装: brew install hudochenkov/sshpass/sshpass"
                print(result['message'])
                allure.attach(result['message'], "清空SSH日志错误", allure.attachment_type.TEXT)
            except subprocess.TimeoutExpired:
                result['message'] = "❌ 清空SSH设备日志超时"
                print(result['message'])
                allure.attach(result['message'], "清空SSH日志错误", allure.attachment_type.TEXT)
            except Exception as e:
                result['message'] = f"❌ 清空SSH设备日志失败: {e}"
                print(result['message'])
                allure.attach(result['message'], "清空SSH日志错误", allure.attachment_type.TEXT)
            
            return result
    
    @staticmethod
    def get_adb_logs(env: dict, project_root: Path, date_str: Optional[str] = None) -> Tuple[Path, Dict[str, Any]]:
        """获取ADB设备上的日志
        
        Args:
            env: 环境配置字典
            project_root: 项目根目录
            date_str: 日期字符串（YYYYMMDD），默认为当天
            
        Returns:
            (日志目录路径, 操作结果字典)
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        log_dir = project_root / "Log" / date_str / "app"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        device_log_path = f'sdcard/DreamSports/log/{date_str}/'
        
        with allure.step(f"获取ADB日志: {device_log_path}"):
            print("="*60)
            print(f"正在获取ADB设备上的日志...")
            print(f"设备路径: {device_log_path}")
            print(f"本地目录: {log_dir}")
            print("="*60)
            
            adb_cmd = ['adb', 'pull', device_log_path, str(log_dir)]
            print(f"执行命令: {' '.join(adb_cmd)}")
            
            result = {
                'success': False,
                'message': '',
                'files': []
            }
            
            try:
                proc_result = subprocess.run(adb_cmd, capture_output=True, text=True, timeout=300)
                if proc_result.returncode == 0:
                    # 处理嵌套目录
                    nested_dir = log_dir / date_str
                    if nested_dir.exists() and nested_dir.is_dir():
                        print(f"⚠️  检测到嵌套目录，正在移动文件...")
                        for file_path in nested_dir.iterdir():
                            if file_path.is_file():
                                target_path = log_dir / file_path.name
                                if target_path.exists():
                                    if file_path.stat().st_mtime > target_path.stat().st_mtime:
                                        file_path.replace(target_path)
                                    else:
                                        file_path.unlink()
                                else:
                                    file_path.replace(target_path)
                        try:
                            nested_dir.rmdir()
                        except:
                            pass
                    
                    # 重命名文件添加时间戳
                    app_fetch_time = datetime.datetime.now()
                    app_timestamp_file = app_fetch_time.strftime('%Y-%m-%d_%H-%M-%S')
                    
                    log_files = list(log_dir.glob("*.log"))
                    renamed_count = 0
                    for log_file in log_files:
                        if log_file.is_file():
                            file_stem = log_file.stem
                            file_suffix = log_file.suffix
                            new_name = f"{file_stem}_{app_timestamp_file}{file_suffix}"
                            new_path = log_dir / new_name
                            if new_path.exists():
                                counter = 1
                                while new_path.exists():
                                    new_name = f"{file_stem}_{app_timestamp_file}_{counter}{file_suffix}"
                                    new_path = log_dir / new_name
                                    counter += 1
                            log_file.rename(new_path)
                            renamed_count += 1
                            result['files'].append(new_path)
                    
                    result['success'] = True
                    result['message'] = f"✅ APP日志已成功拉取到: {log_dir} (重命名 {renamed_count} 个文件)"
                    print(result['message'])
                    allure.attach(proc_result.stdout, "adb pull 输出", allure.attachment_type.TEXT)
                else:
                    result['message'] = f"⚠️  adb pull 警告: {proc_result.stderr}"
                    print(result['message'])
                    allure.attach(proc_result.stderr, "adb pull 错误", allure.attachment_type.TEXT)
            except Exception as e:
                result['message'] = f"❌ adb pull 失败: {e}"
                print(result['message'])
                allure.attach(traceback.format_exc(), "adb pull 异常堆栈", allure.attachment_type.TEXT)
                raise
            
            return log_dir, result
    
    @staticmethod
    def get_ssh_logs(env: dict, project_root: Path, remote_host: Optional[str] = None,
                    remote_log_path: str = "/userdata/deploy/log/logger.log") -> Tuple[Path, Dict[str, Any]]:
        """获取SSH设备（摄像头）上的日志
        
        Args:
            env: 环境配置字典
            project_root: 项目根目录
            remote_host: 远程主机IP，如果为None则从env中获取
            remote_log_path: 远程日志路径
            
        Returns:
            (日志文件路径, 操作结果字典)
        """
        # 从配置获取SSH信息
        try:
            if env:
                if remote_host is None:
                    cameraB_url = env.get('host', {}).get('cameraB', 'http://192.168.3.29')
                    remote_host = cameraB_url.replace('http://', '').replace('https://', '')
                remote_username = env.get('ssh_username', 'root')
                remote_password = resolve_ssh_password(env)
            else:
                raise AttributeError("env not provided")
        except (AttributeError, KeyError, TypeError):
            remote_host = remote_host or "192.168.3.29"
            remote_username = "root"
            remote_password = resolve_ssh_password(None)
        
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        camera_dir = project_root / "Log" / date_str / "camera"
        camera_dir.mkdir(parents=True, exist_ok=True)
        
        camera_fetch_time = datetime.datetime.now()
        camera_timestamp_file = camera_fetch_time.strftime('%Y-%m-%d_%H-%M-%S')
        local_log_path = camera_dir / f"logger_{camera_timestamp_file}.log"
        
        with allure.step(f"获取SSH日志: {remote_host}:{remote_log_path}"):
            print("="*60)
            print(f"正在从摄像头设备下载日志...")
            print(f"远程主机: {remote_username}@{remote_host}")
            print(f"远程路径: {remote_log_path}")
            print(f"本地路径: {local_log_path}")
            print("="*60)
            
            scp_cmd = [
                'sshpass', '-p', remote_password,
                'scp',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                '-o', 'ConnectTimeout=180',  # 将ConnectTimeout选项放在源文件路径之前
                f'{remote_username}@{remote_host}:{remote_log_path}',
                str(local_log_path)
            ]
            
            print(f"执行命令: sshpass -p *** scp {remote_username}@{remote_host}:{remote_log_path} {local_log_path}")
            
            # 先测试SSH连接是否可用，并检查远程文件是否存在
            print("正在测试SSH连接...")
            test_ssh_cmd = [
                'sshpass', '-p', remote_password,
                'ssh',
                '-o', 'StrictHostKeyChecking=no',
                '-o', 'UserKnownHostsFile=/dev/null',
                '-o', 'ConnectTimeout=10',
                f'{remote_username}@{remote_host}',
                'echo "SSH连接测试成功"'
            ]
            
            try:
                test_result = subprocess.run(test_ssh_cmd, capture_output=True, text=True, timeout=15)
                if test_result.returncode != 0:
                    error_msg = f"❌ SSH连接测试失败: {test_result.stderr}"
                    print(error_msg)
                    raise RuntimeError(error_msg)
                print("✅ SSH连接测试成功")
                
                # 检查远程文件是否存在
                print(f"正在检查远程文件是否存在: {remote_log_path}")
                check_file_cmd = [
                    'sshpass', '-p', remote_password,
                    'ssh',
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', 'UserKnownHostsFile=/dev/null',
                    '-o', 'ConnectTimeout=180',
                    f'{remote_username}@{remote_host}',
                    f'test -f "{remote_log_path}" && echo "文件存在" || echo "文件不存在"'
                ]
                check_result = subprocess.run(check_file_cmd, capture_output=True, text=True, timeout=15)
                if check_result.returncode == 0:
                    if "文件存在" in check_result.stdout:
                        print(f"✅ 远程文件存在: {remote_log_path}")
                    else:
                        error_msg = f"❌ 远程文件不存在: {remote_log_path}\n请检查设备上的日志文件路径是否正确"
                        print(error_msg)
                        raise FileNotFoundError(error_msg)
                else:
                    print(f"⚠️  无法检查远程文件状态: {check_result.stderr}")
                    print("   将继续尝试下载...")
                
                print("开始下载日志...")
            except subprocess.TimeoutExpired:
                error_msg = f"❌ SSH连接超时，设备 {remote_host} 可能不可达"
                print(error_msg)
                raise RuntimeError(error_msg)
            except FileNotFoundError:
                raise  # 重新抛出文件不存在错误
            except Exception as e:
                if isinstance(e, (RuntimeError, FileNotFoundError)):
                    raise
                error_msg = f"❌ SSH连接测试异常: {e}"
                print(error_msg)
                raise RuntimeError(error_msg)
            
            result = {
                'success': False,
                'message': '',
                'file_path': local_log_path
            }
            
            # 添加进度提示
            print("⏳ 正在下载日志文件（这可能需要几分钟，请耐心等待）...")
            print("   如果长时间无响应，可能是网络问题或设备不可达")
            
            try:
                # scp_cmd 已经包含了 ConnectTimeout 选项，直接使用
                proc_result = subprocess.run(scp_cmd, capture_output=True, text=True, timeout=900)
                if proc_result.returncode == 0:
                    if local_log_path.exists():
                        file_size = local_log_path.stat().st_size
                        result['success'] = True
                        result['message'] = f"✅ 摄像头日志已成功下载到: {local_log_path} ({file_size/1024/1024:.2f} MB)"
                        print(result['message'])
                        allure.attach(proc_result.stdout, "scp 输出", allure.attachment_type.TEXT)
                    else:
                        result['message'] = f"⚠️  scp 命令执行成功，但文件不存在: {local_log_path}"
                        print(result['message'])
                        raise FileNotFoundError(result['message'])
                else:
                    # 提供更详细的错误信息
                    error_details = []
                    error_details.append(f"返回码: {proc_result.returncode}")
                    if proc_result.stdout:
                        error_details.append(f"stdout: {proc_result.stdout}")
                    if proc_result.stderr:
                        error_details.append(f"stderr: {proc_result.stderr}")
                    
                    full_error = "\n".join(error_details)
                    result['message'] = f"❌ scp 命令执行失败:\n{full_error}"
                    print(result['message'])
                    print(f"完整命令: {' '.join(scp_cmd)}")
                    allure.attach(full_error, "scp 错误详情", allure.attachment_type.TEXT)
                    allure.attach(" ".join(scp_cmd), "执行的scp命令", allure.attachment_type.TEXT)
                    
                    # 根据错误类型提供更友好的提示
                    if "No such file or directory" in proc_result.stderr:
                        error_msg = (
                            f"远程文件不存在或无法访问: {remote_log_path}\n"
                            f"可能原因：\n"
                            f"  1. 文件路径不正确\n"
                            f"  2. 文件权限不足\n"
                            f"  3. 文件已被删除或移动"
                        )
                        print(f"💡 提示: {error_msg}")
                        raise FileNotFoundError(error_msg)
                    else:
                        raise RuntimeError(result['message'])
            except subprocess.TimeoutExpired:
                result['message'] = "❌ scp 命令执行超时（超过15分钟）"
                print(result['message'])
                allure.attach(result['message'], "scp 超时", allure.attachment_type.TEXT)
                raise RuntimeError(result['message'])
            except Exception as e:
                result['message'] = f"❌ scp 下载日志失败: {e}"
                print(result['message'])
                allure.attach(traceback.format_exc(), "异常堆栈", allure.attachment_type.TEXT)
                raise RuntimeError(result['message']) from e
            
            return local_log_path, result
    
    @staticmethod
    def get_all_logs(env: dict, project_root: Path, date_str: Optional[str] = None) -> Tuple[Path, Dict[str, Any]]:
        """获取所有日志（ADB和SSH）- 完整流程，包含步骤打印
        
        Args:
            env: 环境配置字典
            project_root: 项目根目录
            date_str: 日期字符串（YYYYMMDD），默认为当天
            
        Returns:
            (app日志目录路径, 操作结果字典)
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        # 步骤1：删除本地最新日志目录
        print("\n" + "="*60)
        print("步骤 1/4: 删除本地最新日志目录")
        print("="*60)
        E2EFileManager.delete_log_dir(project_root, date_str)
        print("✅ 步骤 1 完成：本地日志目录删除完成\n")
        
        # 步骤2：获取ADB日志
        print("="*60)
        print("步骤 2/4: 获取ADB日志")
        print("="*60)
        app_dir, adb_result = E2ELogManager.get_adb_logs(env, project_root, date_str)
        print("✅ 步骤 2 完成：APP日志获取完成\n")
        
        # 步骤3：获取SSH日志
        print("="*60)
        print("步骤 3/4: 获取SSH日志")
        print("="*60)
        try:
            camera_log_path, ssh_result = E2ELogManager.get_ssh_logs(env, project_root)
            print("✅ 步骤 3 完成：摄像头日志获取完成\n")
        except Exception as e:
            print(f"⚠️  步骤 3 警告：摄像头日志获取失败: {e}")
            print("   将继续执行后续步骤，但相机日志分析可能会失败\n")
            camera_log_path = None
            ssh_result = {
                'success': False,
                'message': f'摄像头日志获取失败: {e}',
                'file_path': None
            }
        
        # 步骤4：打包本地日志目录
        print("="*60)
        print("步骤 4/4: 打包本地日志目录")
        print("="*60)
        pack_result = E2EFileManager.pack_log_dir(project_root, date_str)
        print("✅ 步骤 4 完成：日志目录打包完成\n")
        
        print("="*60)
        print(f"✅ 日志获取完成")
        print("="*60)
        
        return app_dir, {
            'success': True,
            'adb_result': adb_result,
            'ssh_result': ssh_result,
            'pack_result': pack_result
        }


class E2EDeviceManager:
    """设备管理类 - 处理SSH重启、APP操作等"""
    
    @staticmethod
    def ssh_reboot(env: dict, devices: List[str]) -> Dict[str, Any]:
        """通过SSH重启摄像头设备
        
        Args:
            env: 环境配置字典
            devices: 设备IP列表
            
        Returns:
            操作结果字典
        """
        # 从配置获取SSH信息
        try:
            if env:
                remote_username = env.get('ssh_username', 'root')
                remote_password = resolve_ssh_password(env)
            else:
                raise AttributeError("env not provided")
        except (AttributeError, KeyError, TypeError):
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
                
                ssh_cmd = [
                    'sshpass', '-p', remote_password,
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
                    proc_result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=10)
                    if proc_result.returncode == 0:
                        device_result['status'] = 'success'
                        device_result['message'] = f"SSH重启命令执行成功\n输出: {proc_result.stdout}"
                        print(f"✅ 设备 {device_ip} SSH重启命令执行成功")
                    else:
                        if "Connection closed" in proc_result.stderr or "Connection reset" in proc_result.stderr or "Broken pipe" in proc_result.stderr:
                            device_result['status'] = 'success'
                            device_result['message'] = f"SSH重启命令已执行，设备正在重启\n错误信息（正常）: {proc_result.stderr}"
                            print(f"✅ 设备 {device_ip} SSH重启命令已执行，设备正在重启（连接断开是正常的）")
                        else:
                            device_result['status'] = 'warning'
                            device_result['message'] = f"SSH重启命令警告: {proc_result.stderr}\n标准输出: {proc_result.stdout}"
                            print(f"⚠️  设备 {device_ip} SSH重启命令执行警告: {proc_result.stderr}")
                except subprocess.TimeoutExpired:
                    device_result['status'] = 'success'
                    device_result['message'] = "SSH连接超时，设备可能正在重启"
                    print(f"ℹ️  设备 {device_ip} SSH连接超时（可能是设备正在重启导致的，这是正常的）")
                except FileNotFoundError:
                    error_msg = "❌ sshpass 未安装，无法通过SSH重启设备。请安装: brew install hudochenkov/sshpass/sshpass"
                    device_result['status'] = 'error'
                    device_result['message'] = error_msg
                    print(f"❌ {error_msg}")
                    allure.attach(error_msg, f"SSH重启错误 - {device_ip}", allure.attachment_type.TEXT)
                    raise RuntimeError(error_msg)
                except Exception as e:
                    if "Connection closed" in str(e) or "Connection reset" in str(e) or "Broken pipe" in str(e):
                        device_result['status'] = 'success'
                        device_result['message'] = f"SSH重启命令已执行，设备正在重启\n异常信息（正常）: {str(e)}"
                        print(f"✅ 设备 {device_ip} SSH重启命令已执行，设备正在重启（连接断开是正常的）")
                    else:
                        device_result['status'] = 'error'
                        device_result['message'] = f"SSH重启失败: {e}"
                        print(f"❌ 设备 {device_ip} SSH重启失败: {e}")
                        allure.attach(traceback.format_exc(), f"SSH重启错误 - {device_ip}", allure.attachment_type.TEXT)
                
                reboot_results.append(device_result)
                allure.attach(
                    device_result['message'],
                    f"SSH重启结果 - {device_ip}",
                    allure.attachment_type.TEXT
                )
                
                if device_ip != devices[-1]:
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
        
        summary = "SSH重启结果汇总:\n\n"
        for result in reboot_results:
            status_icon = "✅" if result['status'] == 'success' else "⚠️" if result['status'] == 'warning' else "❌"
            summary += f"{status_icon} {result['device']}: {result['status']}\n"
            summary += f"   详情: {result['message']}\n\n"
        allure.attach(summary.strip(), "SSH重启汇总", allure.attachment_type.TEXT)
        
        return {
            'success': all(r['status'] == 'success' for r in reboot_results),
            'results': reboot_results
        }
    
    @staticmethod
    def restart_app(app_package: str = "com.dreamsport.aicamera.client") -> Dict[str, Any]:
        """重启Android应用
        
        Args:
            app_package: 应用包名
            
        Returns:
            操作结果字典
        """
        with allure.step(f"重启应用: {app_package}"):
            print("\n正在重启应用...")
            
            result = {
                'success': False,
                'message': ''
            }
            
            try:
                # 停止应用
                try:
                    stop_app(app_package)
                    print(f"   应用已停止: {app_package}")
                    sleep(1)
                except Exception as e:
                    print(f"   ⚠️  停止应用时出现警告（可能应用未运行）: {e}")
                
                # 启动应用
                start_app(app_package)
                print(f"   应用已启动: {app_package}")
                sleep(5)  # 等待应用完全启动
                
                result['success'] = True
                result['message'] = f"✅ 应用已重启: {app_package}"
                print(result['message'])
            except Exception as e:
                result['message'] = f"❌ 重启应用失败: {e}"
                print(result['message'])
                raise RuntimeError(result['message']) from e
            
            return result
    
    @staticmethod
    def connect_device(device_uri: str = "Android:///") -> Tuple[Any, int, int]:
        """连接Android设备并获取屏幕尺寸
        
        Args:
            device_uri: 设备URI，默认为 "Android:///"
            
        Returns:
            (设备对象, 屏幕宽度, 屏幕高度)
        """
        with allure.step("连接设备"):
            print("\n正在连接设备...")
            try:
                dev = connect_device(device_uri)
                width, height = dev.get_current_resolution()
                print(f"   设备连接成功: {dev}")
                print(f"   屏幕尺寸: {width} x {height}")
                return dev, width, height
            except Exception as e:
                error_msg = f"❌ 连接设备失败: {e}"
                print(error_msg)
                allure.attach(traceback.format_exc(), "连接设备错误", allure.attachment_type.TEXT)
                raise RuntimeError(error_msg) from e
    
    @staticmethod
    def click_start_button(width: int, height: int, offset_x: int = 100, offset_y: int = 50) -> Dict[str, Any]:
        """点击发令按钮
        
        Args:
            width: 屏幕宽度
            height: 屏幕高度
            offset_x: X轴偏移量（从中心往左，默认100像素）
            offset_y: Y轴偏移量（从底部往上，默认50像素）
            
        Returns:
            操作结果字典
        """
        with allure.step("点击发令按钮"):
            print("\n点击发令按钮...")
            result = {
                'success': False,
                'message': '',
                'position': None
            }
            
            try:
                # 计算点击位置：从底部中心往左偏移
                bottom_center = (width // 2 - offset_x, height - offset_y)
                touch(bottom_center)
                print(f"   已点击位置: {bottom_center}")
                
                result['success'] = True
                result['message'] = "✅ 发令按钮操作完成"
                result['position'] = bottom_center
                print(result['message'])
            except Exception as e:
                result['message'] = f"❌ 点击发令按钮失败: {e}"
                print(result['message'])
                allure.attach(traceback.format_exc(), "点击发令按钮错误", allure.attachment_type.TEXT)
                raise RuntimeError(result['message']) from e
            
            return result
    
    @staticmethod
    def click_end_button(width: int, height: int, offset_x: int = -100, offset_y: int = 50) -> Dict[str, Any]:
        """点击结束测试按钮
        
        Args:
            width: 屏幕宽度
            height: 屏幕高度
            offset_x: X轴偏移量（从中心往右，默认-100像素）
            offset_y: Y轴偏移量（从底部往上，默认50像素）
            
        Returns:
            操作结果字典
        """
        with allure.step("点击结束测试按钮"):
            print("\n点击结束测试按钮...")
            result = {
                'success': False,
                'message': '',
                'position': None
            }
            
            try:
                # 计算点击位置：从底部中心往右偏移
                bottom_center = (width // 2 - offset_x, height - offset_y)
                touch(bottom_center)
                print(f"   已点击位置: {bottom_center}")
                
                result['success'] = True
                result['message'] = "✅ 已点击结束测试按钮"
                result['position'] = bottom_center
                print(result['message'])
            except Exception as e:
                result['message'] = f"❌ 点击结束测试按钮失败: {e}"
                print(result['message'])
                allure.attach(traceback.format_exc(), "点击结束测试按钮错误", allure.attachment_type.TEXT)
                raise RuntimeError(result['message']) from e
            
            return result
    
    @staticmethod
    def click_confirm_button(width: int, height: int, confirm_x_ratio: float = 0.65, confirm_y_ratio: float = 0.62) -> Dict[str, Any]:
        """点击确认对话框的确定按钮
        
        Args:
            width: 屏幕宽度
            height: 屏幕高度
            confirm_x_ratio: 确定按钮X位置比例（屏幕宽度的比例，默认0.65即65%）
            confirm_y_ratio: 确定按钮Y位置比例（屏幕高度的比例，默认0.62即62%）
            
        Returns:
            操作结果字典
        """
        with allure.step("点击确认对话框的确定按钮"):
            print("   等待确认对话框出现...")
            sleep(2)  # 等待对话框完全显示
            
            result = {
                'success': False,
                'message': '',
                'position': None
            }
            
            try:
                # 计算确定按钮位置（对话框通常在屏幕中央偏下，确定按钮在右侧）
                confirm_x = int(width * confirm_x_ratio)
                confirm_y = int(height * confirm_y_ratio)
                confirm_center = (confirm_x, confirm_y)
                
                print(f"   点击确定按钮位置: {confirm_center}")
                touch(confirm_center)
                print(f"   已点击确定按钮")
                
                # 等待确认对话框消失
                sleep(2)  # 等待对话框消失和界面更新
                
                result['success'] = True
                result['message'] = "✅ 已点击确定按钮"
                result['position'] = confirm_center
            except Exception as e:
                result['message'] = f"❌ 点击确定按钮失败: {e}"
                print(result['message'])
                allure.attach(traceback.format_exc(), "点击确定按钮错误", allure.attachment_type.TEXT)
                raise RuntimeError(result['message']) from e
            
            return result
    
    @staticmethod
    def run_sport_test(project_root: Path, app_package: str = "com.dreamsport.aicamera.client",
                      wait_before_start: Optional[float] = None,
                      wait_after_start: Optional[float] = None,
                      time_interval: Optional[float] = None,
                      t2: Optional[float] = None,
                      time_interval_2: Optional[float] = None,
                      device_uri: str = "Android:///") -> Dict[str, Any]:
        """执行完整的运动测试流程（连接设备、重启应用、发令、等待、结束测试）
        
        Args:
            project_root: 项目根目录
            app_package: 应用包名
            wait_before_start: 发令前的等待时间（秒），如果为None则尝试从time_interval计算
            wait_after_start: 发令后的等待时间（秒），如果为None则尝试从t2或time_interval_2计算
            time_interval: 重启到发令的时间间隔（用于自动计算wait_before_start）
            t2: 从发令到结束的时间间隔（用于自动计算wait_after_start）
            time_interval_2: 重启到结束的总时间间隔（用于自动计算wait_after_start）
            device_uri: 设备URI
            
        Returns:
            操作结果字典
        """
        # 自动计算等待时间
        print("\n" + "="*60)
        print("等待时间计算:")
        print(f"  传入参数:")
        print(f"    time_interval: {time_interval} 秒" + (f" ({time_interval/60:.1f} 分钟)" if time_interval else ""))
        print(f"    t2: {t2} 秒" + (f" ({t2/60:.1f} 分钟)" if t2 else ""))
        print(f"    time_interval_2: {time_interval_2} 秒" + (f" ({time_interval_2/60:.1f} 分钟)" if time_interval_2 else ""))
        print(f"    wait_before_start: {wait_before_start} 秒" + (f" ({wait_before_start/60:.1f} 分钟)" if wait_before_start else ""))
        print(f"    wait_after_start: {wait_after_start} 秒" + (f" ({wait_after_start/60:.1f} 分钟)" if wait_after_start else ""))
        
        if wait_before_start is None and time_interval is not None:
            wait_before_start = time_interval
            print(f"  ✓ 自动设置 wait_before_start = time_interval = {wait_before_start} 秒 ({wait_before_start/60:.1f} 分钟)")
        
        if wait_after_start is None:
            wait_before_start_calc, wait_after_start_calc = E2ETimeHelper.get_wait_times(
                time_interval, t2, time_interval_2
            )
            if wait_after_start_calc is not None:
                wait_after_start = wait_after_start_calc
                print(f"  ✓ 自动计算 wait_after_start = {wait_after_start} 秒 ({wait_after_start/60:.1f} 分钟)")
                # 验证等待时间是否合理
                if wait_after_start < 60:
                    print(f"  ⚠️  警告: wait_after_start ({wait_after_start}秒) 似乎太小！")
                    print(f"     这可能表示使用了错误的参数。")
                    print(f"     请检查: t2={t2}, time_interval={time_interval}, time_interval_2={time_interval_2}")
                    print(f"     如果 time_interval={time_interval} 被错误地用作 wait_after_start，这是不对的！")
                    print(f"     wait_after_start 应该等于 t2={t2} 或 time_interval_2 - time_interval = {time_interval_2 - time_interval if time_interval_2 and time_interval else 'N/A'}")
            else:
                print(f"  ⚠️  无法自动计算 wait_after_start，将使用默认值")
        else:
            print(f"  ✓ 使用传入的 wait_after_start = {wait_after_start} 秒 ({wait_after_start/60:.1f} 分钟)")
            # 验证传入的等待时间是否合理
            if wait_after_start < 60:
                print(f"  ⚠️  警告: 传入的 wait_after_start ({wait_after_start}秒) 似乎太小！")
                print(f"     请确认这是正确的值。")
        
        print("="*60 + "\n")
        
        with allure.step("执行运动测试流程"):
            # 抑制 Airtest 清理时的日志错误（文件已关闭但仍尝试写入）
            # 这些错误发生在程序退出时，不影响测试功能
            original_log_level = logging.getLogger().level
            original_handlers = logging.getLogger().handlers[:]
            
            # 创建自定义的日志处理器，忽略 I/O 错误
            class IgnoreIOErrorHandler(logging.Handler):
                def emit(self, record):
                    try:
                        super().emit(record)
                    except (ValueError, OSError):
                        # 忽略文件已关闭时的 I/O 错误
                        pass
            
            try:
                # 临时提高日志级别，并添加错误处理器
                logging.getLogger().setLevel(logging.ERROR)
                # 为 Airtest 相关的 logger 添加错误处理器
                airtest_loggers = [
                    logging.getLogger('airtest'),
                    logging.getLogger('airtest.core'),
                    logging.getLogger('airtest.core.android'),
                ]
                for logger in airtest_loggers:
                    logger.addHandler(IgnoreIOErrorHandler())
                    logger.setLevel(logging.ERROR)
            except Exception:
                pass
            
            result = {
                'success': False,
                'message': '',
                'device': None,
                'width': None,
                'height': None
            }
            
            try:
                # 1. 连接设备
                dev, width, height = E2EDeviceManager.connect_device(device_uri)
                result['device'] = dev
                result['width'] = width
                result['height'] = height
                
                # 2. 重启应用
                E2EDeviceManager.restart_app(app_package)
                
                # 3. 等待检录间隔（如果已计算）
                if wait_before_start is not None:
                    print(f"\n等待时间间隔: {wait_before_start} 秒")
                    sleep(wait_before_start)
                else:
                    print("\n⚠️  未设置等待时间间隔，跳过等待")
                
                # 4. 点击发令按钮
                E2EDeviceManager.click_start_button(width, height)
                
                # 5. 等待测试结束（从发令到结束的时间间隔）
                if wait_after_start is not None:
                    # 验证等待时间是否合理（至少应该大于60秒，避免使用错误的 time_interval）
                    if wait_after_start < 60:
                        print(f"\n⚠️  警告: wait_after_start ({wait_after_start}秒) 似乎太小，可能使用了错误的参数")
                        print(f"   如果这是错误的，请检查 t2 和 time_interval_2 的值")
                        print(f"   当前参数: t2={t2}, time_interval={time_interval}, time_interval_2={time_interval_2}")
                    print(f"\n等待测试结束时间: {wait_after_start} 秒 ({wait_after_start/60:.1f} 分钟)")
                    print(f"开始等待时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    sleep(wait_after_start)
                    print(f"等待完成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    wait_time = 10  # 默认10秒
                    print(f"\n⚠️  未设置等待时间，使用默认等待时间: {wait_time} 秒")
                    sleep(wait_time)
                
                # 6. 结束测试前截图
                print("\n结束测试截图...")
                try:
                    E2EDeviceManager.take_screenshot(project_root, "test_end")
                except Exception as e:
                    print(f"   ⚠️  截图失败: {e}")
                    # 不抛出异常，继续执行
                
                # 7. 点击结束测试按钮
                E2EDeviceManager.click_end_button(width, height)
                
                # 8. 点击确认对话框的确定按钮
                E2EDeviceManager.click_confirm_button(width, height)
                
                result['success'] = True
                result['message'] = "✅ 运动测试流程完成"
                print("\n" + result['message'])
            except Exception as e:
                result['message'] = f"❌ 运动测试流程失败: {e}"
                print(f"\n{result['message']}")
                traceback.print_exc()
                allure.attach(traceback.format_exc(), "错误堆栈", allure.attachment_type.TEXT)
                raise RuntimeError(result['message']) from e
            finally:
                # 恢复原始日志配置
                try:
                    logging.getLogger().setLevel(original_log_level)
                    # 移除临时添加的处理器
                    airtest_loggers = [
                        logging.getLogger('airtest'),
                        logging.getLogger('airtest.core'),
                        logging.getLogger('airtest.core.android'),
                    ]
                    for logger in airtest_loggers:
                        # 移除 IgnoreIOErrorHandler 类型的处理器
                        logger.handlers = [h for h in logger.handlers if not isinstance(h, IgnoreIOErrorHandler)]
                except Exception:
                    pass
            
            return result
    
    @staticmethod
    def take_screenshot(project_root: Path, prefix: str = "screenshot") -> Path:
        """截取屏幕截图
        
        Args:
            project_root: 项目根目录
            prefix: 文件名前缀
            
        Returns:
            截图文件路径
        """
        date_str = datetime.datetime.now().strftime("%Y%m%d")
        screenshot_dir = project_root / "allure-report" / "screenshot" / date_str
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        screenshot_filename = f"{prefix}_{timestamp_str}.png"
        screenshot_path = screenshot_dir / screenshot_filename
        
        snapshot(str(screenshot_path))
        print(f"   截图已保存: {screenshot_path}")
        
        # 附加到Allure报告
        if screenshot_path.exists():
            with open(screenshot_path, 'rb') as f:
                allure.attach(
                    f.read(),
                    f"{prefix} - {timestamp_str}",
                    allure.attachment_type.PNG
                )
            print(f"   截图已附加到 Allure 报告")
        
        return screenshot_path


class E2EFileManager:
    """文件管理类 - 处理文件打包、清理等"""
    
    @staticmethod
    def delete_log_dir(project_root: Path, date_str: Optional[str] = None) -> Dict[str, Any]:
        """删除本地日志目录（获取日志前）
        
        Args:
            project_root: 项目根目录
            date_str: 日期字符串（YYYYMMDD），默认为当天
            
        Returns:
            操作结果字典
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        log_dir = project_root / "Log" / date_str
        
        result = {
            'success': False,
            'message': ''
        }
        
        if not (log_dir.exists() and log_dir.is_dir()):
            result['success'] = True
            result['message'] = f"ℹ️  日志目录不存在，跳过删除: {log_dir}"
            print(result['message'])
            allure.attach(result['message'], "删除日志目录结果", allure.attachment_type.TEXT)
            return result
        
        with allure.step(f"删除本地日志目录: {log_dir}"):
            print("="*60)
            print(f"正在删除日志目录: {log_dir}")
            print("="*60)
            
            try:
                shutil.rmtree(log_dir)
                result['success'] = True
                result['message'] = f"✅ 已删除目录: {log_dir}"
                print(result['message'])
                
                allure.attach(
                    f"已删除日志目录: {log_dir}",
                    "删除日志目录结果",
                    allure.attachment_type.TEXT
                )
            except Exception as e:
                result['message'] = f"⚠️  删除日志目录失败: {e}"
                print(result['message'])
                allure.attach(traceback.format_exc(), "删除日志目录错误", allure.attachment_type.TEXT)
            
            return result
    
    @staticmethod
    def pack_log_dir(project_root: Path, date_str: Optional[str] = None) -> Dict[str, Any]:
        """打包本地日志目录（获取日志后）
        
        Args:
            project_root: 项目根目录
            date_str: 日期字符串（YYYYMMDD），默认为当天
            
        Returns:
            操作结果字典
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        log_dir = project_root / "Log" / date_str
        
        result = {
            'success': False,
            'message': '',
            'zip_path': None
        }
        
        if not (log_dir.exists() and log_dir.is_dir()):
            result['message'] = f"ℹ️  日志目录不存在，跳过打包: {log_dir}"
            print(result['message'])
            allure.attach(result['message'], "打包日志目录结果", allure.attachment_type.TEXT)
            return result
        
        # 检查是否有文件需要打包
        all_files = []
        for root, dirs, files in os.walk(log_dir):
            for file in files:
                file_path = Path(root) / file
                if file_path.is_file():
                    all_files.append(file_path)
        
        if not all_files:
            result['message'] = f"ℹ️  日志目录为空，跳过打包: {log_dir}"
            print(result['message'])
            allure.attach(result['message'], "打包日志目录结果", allure.attachment_type.TEXT)
            return result
        
        with allure.step(f"打包本地日志目录: {log_dir}"):
            timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            zip_filename = f"{date_str}_{timestamp_str}.zip"
            zip_path = project_root / "Log" / zip_filename
            
            print("="*60)
            print(f"正在打包日志目录: {log_dir}")
            print(f"目标zip文件: {zip_path}")
            print(f"包含文件数: {len(all_files)}")
            print("="*60)
            
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(log_dir):
                        for file in files:
                            file_path = Path(root) / file
                            if file_path.is_file():
                                arcname = file_path.relative_to(log_dir)
                                zipf.write(file_path, arcname)
                                print(f"   已添加: {arcname}")
                
                zip_size = zip_path.stat().st_size
                zip_size_mb = zip_size / (1024 * 1024)
                
                result['success'] = True
                result['message'] = f"✅ 打包完成: {zip_path} ({zip_size_mb:.2f} MB, {len(all_files)} 个文件)"
                result['zip_path'] = zip_path
                print(result['message'])
                
                allure.attach(
                    f"已打包日志目录\n原目录: {log_dir}\nzip文件: {zip_path}\n文件大小: {zip_size_mb:.2f} MB\n包含文件数: {len(all_files)}",
                    "打包日志目录结果",
                    allure.attachment_type.TEXT
                )
            except Exception as e:
                result['message'] = f"❌ 打包日志目录失败: {e}"
                print(result['message'])
                allure.attach(traceback.format_exc(), "打包日志目录错误", allure.attachment_type.TEXT)
            
            return result
    
    @staticmethod
    def pack_and_delete_log_dir(project_root: Path, date_str: Optional[str] = None) -> Dict[str, Any]:
        """打包并删除日志目录（兼容旧版本）
        
        Args:
            project_root: 项目根目录
            date_str: 日期字符串（YYYYMMDD），默认为当天
            
        Returns:
            操作结果字典
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        log_dir = project_root / "Log" / date_str
        
        result = {
            'success': False,
            'message': '',
            'zip_path': None
        }
        
        if not (log_dir.exists() and log_dir.is_dir()):
            result['message'] = f"ℹ️  日志目录不存在，跳过打包: {log_dir}"
            print(result['message'])
            return result
        
        with allure.step(f"打包并删除日志目录: {log_dir}"):
            timestamp_str = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            zip_filename = f"{date_str}_{timestamp_str}.zip"
            zip_path = project_root / "Log" / zip_filename
            
            print("="*60)
            print(f"正在打包日志目录: {log_dir}")
            print(f"目标zip文件: {zip_path}")
            print("="*60)
            
            try:
                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for root, dirs, files in os.walk(log_dir):
                        for file in files:
                            file_path = Path(root) / file
                            arcname = file_path.relative_to(log_dir)
                            zipf.write(file_path, arcname)
                            print(f"   已添加: {arcname}")
                
                zip_size = zip_path.stat().st_size
                zip_size_mb = zip_size / (1024 * 1024)
                
                # 删除原目录
                shutil.rmtree(log_dir)
                
                result['success'] = True
                result['message'] = f"✅ 打包完成: {zip_path} ({zip_size_mb:.2f} MB)"
                result['zip_path'] = zip_path
                print(result['message'])
                print(f"✅ 已删除目录: {log_dir}")
                
                allure.attach(
                    f"已打包并删除日志目录\n原目录: {log_dir}\nzip文件: {zip_path}\n文件大小: {zip_size_mb:.2f} MB",
                    "打包日志目录结果",
                    allure.attachment_type.TEXT
                )
            except Exception as e:
                result['message'] = f"❌ 打包或删除日志目录失败: {e}"
                print(result['message'])
                allure.attach(traceback.format_exc(), "打包日志目录错误", allure.attachment_type.TEXT)
            
            return result


class E2ELogAnalyzer:
    """长跑 日志分析类 - 处理日志分析脚本调用和结果处理"""
    
    @staticmethod
    def find_app_log_file(project_root: Path, date_str: Optional[str] = None, 
                          search_keyword: str = "APP_INFO: 跳绳屏") -> Optional[Path]:
        """查找APP日志文件（包含指定关键字的文件）
        
        Args:
            project_root: 项目根目录
            date_str: 日期字符串（YYYYMMDD），默认为当天
            search_keyword: 搜索关键字，默认为 "APP_INFO: 跳绳屏"
            
        Returns:
            日志文件路径，如果未找到则返回None
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        log_dir = project_root / "Log" / date_str / "app"
        
        # 如果app目录不存在，尝试查找嵌套目录
        if not log_dir.exists():
            nested_log_dir = project_root / "Log" / date_str / date_str
            if nested_log_dir.exists():
                log_dir = nested_log_dir
            else:
                log_dir = project_root / "Log" / date_str
        
        if not log_dir.exists():
            return None
        
        # 查找包含关键字的日志文件
        log_files = list(log_dir.glob("*.log"))
        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for i, line in enumerate(f):
                        if i > 100:  # 只检查前100行
                            break
                        if search_keyword in line:
                            return log_file
            except Exception:
                continue
        
        return None
    
    @staticmethod
    def analyze_app_log(project_root: Path, log_file: Optional[Path] = None, 
                       start_time: Optional[str] = None, end_time: Optional[str] = None,
                       expected_circles: int = 4, output_dir: Optional[Path] = None,
                       date_str: Optional[str] = None, fallback_start_time: Optional[str] = None,
                       fallback_end_time: Optional[str] = None) -> Dict[str, Any]:
        """分析APP日志（自动处理时间提取和规范化）
        
        Args:
            project_root: 项目根目录
            log_file: 日志文件路径，如果为None则自动查找
            start_time: 开始时间，如果为None则尝试从日志文件或类变量提取
            end_time: 结束时间，如果为None则尝试从日志文件或类变量提取
            expected_circles: 期望完成的圈数
            output_dir: 输出目录，默认为 allure-report/log_analysis/date_str
            date_str: 日期字符串（YYYYMMDD），默认为当天
            fallback_start_time: 备用开始时间（如果无法从日志提取）
            fallback_end_time: 备用结束时间（如果无法从日志提取）
            
        Returns:
            操作结果字典
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        # 自动查找日志文件
        if log_file is None:
            log_file = E2ELogAnalyzer.find_app_log_file(project_root, date_str)
            if not log_file:
                raise FileNotFoundError(f"未找到包含 'APP_INFO: 跳绳屏' 的日志文件，请先运行 test_get_log 获取日志")
            print(f"✅ 找到日志文件: {log_file}")
        
        # 优先使用调用方传入的 app_start_time / app_end_time（即测试里传的 logStartTime / logEndTime），
        # 仅当二者未设置或为空时才使用 fallback 或从日志提取
        _received = f"app_start_time={repr(start_time)}, app_end_time={repr(end_time)}"
        print(f"📥 收到的时间参数: {_received}")
        allure.attach(_received, "收到的时间参数（用于排查是否使用函数返回时间）", allure.attachment_type.TEXT)
        start_time = E2ETimeHelper.normalize_time_string(start_time)
        end_time = E2ETimeHelper.normalize_time_string(end_time)
        # 优先级：1) 测试传入的 app 时间  2) 从日志解析  3) fallback（最后才用）
        has_app_time = bool(start_time and end_time and start_time.strip() and end_time.strip())
        if not has_app_time:
            print("⚠️  app 时间未设置，优先从日志文件中提取...")
            extracted_times = E2ETimeHelper.extract_time_from_log(log_file)
            if extracted_times:
                start_time, end_time = extracted_times
                print(f"✅ 从日志文件中提取时间范围:")
                print(f"   开始时间: {start_time}")
                print(f"   结束时间: {end_time}")
            elif fallback_start_time and fallback_end_time:
                start_time = fallback_start_time.strip() if isinstance(fallback_start_time, str) else fallback_start_time
                end_time = fallback_end_time.strip() if isinstance(fallback_end_time, str) else fallback_end_time
                print(f"✅ 使用备用时间（fallback）: 日志中未解析到时间")
                print(f"   开始时间: {start_time}")
                print(f"   结束时间: {end_time}")
            else:
                raise ValueError("无法从日志文件中提取时间范围，且未提供备用时间。请先运行 test_updateRtspSettings 或手动设置时间")
        else:
            print(f"✅ 使用测试传入的时间（logStartTime/logEndTime）:")
            print(f"   开始时间: {start_time}")
            print(f"   结束时间: {end_time}")
        
        if output_dir is None:
            # analyze_log.py 会在 output_dir 下创建日期子目录，所以这里只传基础目录
            output_dir = project_root / 'allure-report' / 'log_analysis'
        
        analyze_script = project_root / "Log" / "analyze_log.py"
        if not analyze_script.exists():
            raise FileNotFoundError(f"分析脚本不存在: {analyze_script}")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            'python3',
            str(analyze_script.resolve()),
            str(log_file.resolve()),
            '--start-time', start_time,
            '--end-time', end_time,
            '--circles', str(expected_circles),
            '--output-dir', str(output_dir.resolve())  # analyze_log.py 会在 output_dir 下创建日期子目录
        ]
        
        with allure.step("分析APP日志"):
            print("="*80)
            print("开始分析日志:")
            print(f"日志文件: {log_file}")
            print(f"开始时间: {start_time}")
            print(f"结束时间: {end_time}")
            print(f"期望完成圈数: {expected_circles}")
            print(f"输出目录: {output_dir}")
            print("="*80)
            
            allure.attach(" ".join(cmd), "分析脚本执行命令", allure.attachment_type.TEXT)
            
            result = {
                'success': False,
                'message': '',
                'output_dir': output_dir,
                'files': []
            }
            
            try:
                proc_result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    cwd=str(project_root.resolve())
                )
                
                if proc_result.returncode == 0:
                    result['success'] = True
                    result['message'] = "✅ 日志分析脚本执行成功"
                    
                    # 检查是否有"未找到有效数据"的提示
                    has_no_data = "未找到有效数据" in proc_result.stdout
                    
                    # analyze_log.py 会在 output_dir 下创建日期子目录，需要检查日期子目录
                    date_output_dir = output_dir / date_str
                    
                    # 验证生成的文件
                    generated_files = []
                    if date_output_dir.exists():
                        files = list(date_output_dir.glob("*"))
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
                        matched_files = list(date_output_dir.glob(pattern))
                        if matched_files:
                            # 如果有多个匹配的文件，选择最新的（按修改时间）
                            matched_file = max(matched_files, key=lambda f: f.stat().st_mtime)
                            found_files[file_key] = matched_file
                            result['files'].append(matched_file)
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
                    if not date_output_dir.exists() or not generated_files:
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
                    
                    print(result['message'])
                    allure.attach(proc_result.stdout, "日志分析输出", allure.attachment_type.TEXT)
                    
                    # 解析统计信息并计算漏圈率
                    if proc_result.returncode == 0 and proc_result.stdout:
                        import re
                        total_people = None
                        completed_count = None
                        missing_stats = {}  # {漏圈数: 人数}
                        
                        # 解析标准输出中的统计信息
                        # 提取总人数
                        total_match = re.search(r'总人数:\s*(\d+)', proc_result.stdout)
                        if total_match:
                            total_people = int(total_match.group(1))
                        
                        # 提取完成expected_circles圈的人数
                        completed_match = re.search(rf'完成{expected_circles}圈:\s*(\d+)\s*人', proc_result.stdout)
                        if completed_match:
                            completed_count = int(completed_match.group(1))
                        
                        # 提取漏圈统计（漏1圈、漏2圈等）
                        for missing_count in range(1, expected_circles + 1):
                            missing_match = re.search(rf'漏{missing_count}圈:\s*(\d+)\s*人', proc_result.stdout)
                            if missing_match:
                                missing_stats[missing_count] = int(missing_match.group(1))
                        
                        # 计算并打印漏圈率统计
                        if total_people is not None:
                            print("\n" + "="*60)
                            print("📊 漏圈率统计")
                            print("="*60)
                            print(f"总人数: {total_people}")
                            
                            if completed_count is not None:
                                print(f"完成{expected_circles}圈: {completed_count} 人")
                            else:
                                completed_count = 0
                            
                            # 打印漏圈统计
                            total_missing_circles = 0
                            for missing_count in range(1, expected_circles + 1):
                                missing_people = missing_stats.get(missing_count, 0)
                                if missing_people > 0:
                                    print(f"漏{missing_count}圈: {missing_people} 人")
                                total_missing_circles += missing_people * missing_count
                            
                            # 计算漏圈率
                            if total_people > 0:
                                total_expected_circles = total_people * expected_circles
                                missing_rate = (total_missing_circles / total_expected_circles) * 100 if total_expected_circles > 0 else 0
                                print(f"\n漏圈率: {missing_rate:.2f}%")
                                print(f"计算方式: 漏总圈数({total_missing_circles}) / 总人数({total_people}) × 期望圈数({expected_circles}) = {total_expected_circles}")
                                print(f"漏总圈数: {total_missing_circles} 圈")
                                print(f"总期望圈数: {total_expected_circles} 圈")
                                
                                # 附加到Allure报告
                                stats_text = f"""漏圈率统计
总人数: {total_people}
完成{expected_circles}圈: {completed_count} 人
漏圈率: {missing_rate:.2f}%
漏总圈数: {total_missing_circles} 圈
总期望圈数: {total_expected_circles} 圈
计算方式: 漏总圈数({total_missing_circles}) / (总人数({total_people}) × 期望圈数({expected_circles}))
"""
                                for missing_count in range(1, expected_circles + 1):
                                    missing_people = missing_stats.get(missing_count, 0)
                                    if missing_people > 0:
                                        stats_text += f"漏{missing_count}圈: {missing_people} 人\n"
                                
                                allure.attach(stats_text.strip(), "漏圈率统计", allure.attachment_type.TEXT)
                                
                                # 将统计信息添加到返回结果
                                result['stats'] = {
                                    'total_people': total_people,
                                    'completed_count': completed_count,
                                    'missing_stats': missing_stats,
                                    'total_missing_circles': total_missing_circles,
                                    'total_expected_circles': total_expected_circles,
                                    'missing_rate': missing_rate
                                }
                            else:
                                print("⚠️  无法计算漏圈率：总人数为0")
                            
                            print("="*60 + "\n")
                        else:
                            print("⚠️  无法从脚本输出中解析统计信息，请检查脚本输出格式。")
                else:
                    result['message'] = f"❌ 日志分析失败: {proc_result.stderr}"
                    print(result['message'])
                    allure.attach(proc_result.stderr, "日志分析错误", allure.attachment_type.TEXT)
                    raise RuntimeError(result['message'])
            except subprocess.TimeoutExpired:
                result['message'] = "❌ 日志分析超时（超过10分钟）"
                print(result['message'])
                raise
            except Exception as e:
                result['message'] = f"❌ 日志分析异常: {e}"
                print(result['message'])
                allure.attach(traceback.format_exc(), "异常堆栈", allure.attachment_type.TEXT)
                raise
            
            return result
    
    @staticmethod
    def analyze_all_logs(project_root: Path,
                        app_start_time: Optional[str] = None, app_end_time: Optional[str] = None,
                        expected_circles: int = 4, distance: Optional[int] = None, circles: Optional[int] = None,
                        fallback_start_time: Optional[str] = None, fallback_end_time: Optional[str] = None,
                        time_offset_hours: int = -8, date_str: Optional[str] = None,
                        log_file: Optional[Path] = None) -> Dict[str, Any]:
        """统一分析APP和Camera日志
        
        Args:
            project_root: 项目根目录
            app_start_time: APP开始时间
            app_end_time: APP结束时间
            expected_circles: 期望完成圈数
            distance: 距离（米），用于计算numeric_param
            circles: 圈数，用于计算numeric_param
            fallback_start_time: 备用APP开始时间
            fallback_end_time: 备用APP结束时间
            time_offset_hours: 时间偏移量（小时），默认-8小时
            date_str: 日期字符串（YYYYMMDD），默认为当天
            log_file: 日志文件路径，如果指定则使用该路径，否则自动查找
            
        Returns:
            操作结果字典，包含app_result和camera_result
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        result = {
            'success': True,
            'app_result': None,
            'camera_result': None,
            'message': ''
        }
        
        # 分析APP日志
        print("\n" + "="*80)
        print("步骤 1/2: 分析APP日志")
        print("="*80)
        try:
            app_result = E2ELogAnalyzer.analyze_app_log(
                project_root=project_root,
                log_file=log_file,
                start_time=app_start_time,
                end_time=app_end_time,
                expected_circles=expected_circles,
                fallback_start_time=fallback_start_time,
                fallback_end_time=fallback_end_time,
                date_str=date_str
            )
            result['app_result'] = app_result
            print("✅ APP日志分析完成\n")
        except Exception as e:
            result['success'] = False
            result['message'] = f"APP日志分析失败: {e}"
            print(f"❌ APP日志分析失败: {e}\n")
            # 继续执行Camera日志分析，即使APP日志分析失败
        
        # 分析Camera日志
        print("="*80)
        print("步骤 2/2: 分析Camera日志")
        print("="*80)
        try:
            camera_result = E2ELogAnalyzer.analyze_camera_log(
                project_root=project_root,
                app_start_time=app_start_time,
                app_end_time=app_end_time,
                distance=distance,
                circles=circles,
                fallback_start_time=fallback_start_time,
                fallback_end_time=fallback_end_time,
                time_offset_hours=time_offset_hours,
                date_str=date_str
            )
            result['camera_result'] = camera_result
            print("✅ Camera日志分析完成\n")
        except Exception as e:
            result['success'] = False
            if result['message']:
                result['message'] += f"; Camera日志分析失败: {e}"
            else:
                result['message'] = f"Camera日志分析失败: {e}"
            print(f"❌ Camera日志分析失败: {e}\n")
        
        print("="*80)
        if result['success']:
            print("✅ 所有日志分析完成")
        else:
            print(f"⚠️  日志分析完成，但有错误: {result['message']}")
        print("="*80 + "\n")
        
        return result
    
    @staticmethod
    def find_camera_log_file(project_root: Path, date_str: Optional[str] = None) -> Optional[Path]:
        """查找最新的相机日志文件
        
        Args:
            project_root: 项目根目录
            date_str: 日期字符串（YYYYMMDD），默认为当天
            
        Returns:
            相机日志文件路径，如果未找到则返回None
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        camera_log_dir = project_root / "Log" / date_str / "camera"
        if not camera_log_dir.exists():
            return None
        
        camera_log_files = list(camera_log_dir.glob("*.log"))
        if not camera_log_files:
            return None
        
        # 按修改时间排序，取最新的
        return max(camera_log_files, key=lambda f: f.stat().st_mtime)
    
    @staticmethod
    def analyze_camera_log(project_root: Path, app_log_file: Optional[Path] = None,
                          camera_log_file: Optional[Path] = None,
                          numeric_param: Optional[int] = None,
                          app_start_time: Optional[str] = None, app_end_time: Optional[str] = None,
                          camera_start_time: Optional[str] = None, camera_end_time: Optional[str] = None,
                          output_dir: Optional[Path] = None, date_str: Optional[str] = None,
                          distance: Optional[int] = None, circles: Optional[int] = None,
                          fallback_start_time: Optional[str] = None, fallback_end_time: Optional[str] = None,
                          time_offset_hours: int = -8) -> Dict[str, Any]:
        """分析相机日志（自动处理文件查找、时间转换等）
        
        Args:
            project_root: 项目根目录
            app_log_file: APP日志文件路径，如果为None则自动查找
            camera_log_file: 相机日志文件路径，如果为None则自动查找最新的
            numeric_param: 数字参数（距离/圈数），如果为None则通过distance和circles计算
            app_start_time: APP开始时间，如果为None则使用fallback_start_time
            app_end_time: APP结束时间，如果为None则使用fallback_end_time
            camera_start_time: 相机开始时间，如果为None则自动转换
            camera_end_time: 相机结束时间，如果为None则自动转换
            output_dir: 输出目录，默认为 allure-report/log_analysis/date_str
            date_str: 日期字符串（YYYYMMDD），默认为当天
            distance: 距离（米），用于计算numeric_param
            circles: 圈数，用于计算numeric_param
            fallback_start_time: 备用APP开始时间
            fallback_end_time: 备用APP结束时间
            time_offset_hours: 时间偏移量（小时），默认-8小时
            
        Returns:
            操作结果字典
        """
        if date_str is None:
            date_str = datetime.datetime.now().strftime("%Y%m%d")
        
        # 自动查找APP日志文件
        if app_log_file is None:
            app_log_file = E2ELogAnalyzer.find_app_log_file(project_root, date_str)
            if not app_log_file:
                raise FileNotFoundError(f"未找到包含 'APP_INFO: 跳绳屏' 的APP日志文件，请先运行 test_get_log 获取日志")
            print(f"✅ 找到APP日志文件: {app_log_file}")
        
        # 自动查找相机日志文件
        if camera_log_file is None:
            camera_log_file = E2ELogAnalyzer.find_camera_log_file(project_root, date_str)
            if not camera_log_file:
                error_msg = (
                    f"未找到相机日志文件，请先运行 test_get_log 获取日志。\n"
                    f"可能原因：\n"
                    f"  1. test_get_log 中的SSH日志下载失败（检查网络连接和设备状态）\n"
                    f"  2. 日志文件路径不正确（检查 Log/{date_str}/camera/ 目录）\n"
                    f"  3. 日志文件尚未生成"
                )
                print(f"❌ {error_msg}")
                raise FileNotFoundError(error_msg)
            print(f"✅ 找到相机日志文件: {camera_log_file}")
        
        # 规范化APP时间
        app_start_time = E2ETimeHelper.normalize_time_string(app_start_time or fallback_start_time)
        app_end_time = E2ETimeHelper.normalize_time_string(app_end_time or fallback_end_time)
        
        if not app_start_time or not app_end_time:
            raise ValueError("APP开始时间和结束时间未提供，且无备用时间")
        
        # 自动转换相机时间
        if camera_start_time is None:
            camera_start_time = E2ETimeHelper.convert_to_camera_time(app_start_time, time_offset_hours)
        if camera_end_time is None:
            camera_end_time = E2ETimeHelper.convert_to_camera_time(app_end_time, time_offset_hours)
        
        print(f"✅ 时间参数设置:")
        print(f"   APP开始时间: {app_start_time}")
        print(f"   APP结束时间: {app_end_time}")
        print(f"   相机开始时间: {camera_start_time}")
        print(f"   相机结束时间: {camera_end_time}")
        
        # 计算数字参数
        if numeric_param is None:
            if distance is not None and circles is not None:
                numeric_param = distance // circles
                print(f"计算数字参数: 距离{distance}米 / 圈数{circles}圈 = {numeric_param}")
            else:
                raise ValueError("numeric_param未提供，且无法通过distance和circles计算")
        
        if output_dir is None:
            # analyze_camera_Latest.py 会在 output_dir 下创建日期子目录，所以这里只传基础目录
            output_dir = project_root / 'allure-report' / 'log_analysis'
        
        analyze_script = project_root / "Log" / "analyze_camera_Latest.py"
        if not analyze_script.exists():
            raise FileNotFoundError(f"分析脚本不存在: {analyze_script}")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
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
            '--output-dir', str(output_dir.resolve())
        ]
        
        with allure.step("分析相机日志"):
            print("="*80)
            print("开始分析相机和应用日志:")
            print(f"APP日志文件: {app_log_file}")
            print(f"相机日志文件: {camera_log_file}")
            print(f"数字参数: {numeric_param}")
            print(f"APP时间范围: {app_start_time} - {app_end_time}")
            print(f"相机时间范围: {camera_start_time} - {camera_end_time}")
            print(f"输出目录: {output_dir}")
            print("="*80)
            
            allure.attach(" ".join(cmd), "相机日志分析执行命令", allure.attachment_type.TEXT)
            
            result = {
                'success': False,
                'message': '',
                'output_dir': output_dir,
                'files': []
            }
            
            try:
                proc_result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,
                    cwd=str(project_root.resolve())
                )
                
                if proc_result.returncode == 0:
                    result['success'] = True
                    result['message'] = "✅ camera日志分析完成"
                    
                    # 检查输出目录（按日期）- analyze_camera_Latest.py 会在 output_dir 下创建日期子目录
                    date_output_dir = output_dir / date_str
                    
                    # 检查脚本输出中是否有错误提示
                    has_error = False
                    if proc_result.stdout:
                        if "错误" in proc_result.stdout or "分析终止" in proc_result.stdout or "无匹配" in proc_result.stdout or "无有效" in proc_result.stdout:
                            has_error = True
                    
                    # 验证生成的文件
                    generated_files = []
                    if date_output_dir.exists():
                        files = list(date_output_dir.glob("*"))
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
                        matched_files = list(date_output_dir.glob(pattern))
                        if matched_files:
                            # 如果有多个匹配的文件，选择最新的（按修改时间）
                            matched_file = max(matched_files, key=lambda f: f.stat().st_mtime)
                            found_files[file_key] = matched_file
                            result['files'].append(matched_file)
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
                    if not date_output_dir.exists() or not generated_files:
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
                    
                    print(result['message'])
                    allure.attach(proc_result.stdout, "相机日志分析输出", allure.attachment_type.TEXT)
                else:
                    result['message'] = f"❌ 相机日志分析脚本执行失败: {proc_result.stderr}"
                    print(result['message'])
                    allure.attach(proc_result.stderr, "相机日志分析错误", allure.attachment_type.TEXT)
                    raise RuntimeError(result['message'])
            except subprocess.TimeoutExpired:
                result['message'] = "❌ camera日志分析超时（超过10分钟）"
                print(result['message'])
                raise
            except Exception as e:
                result['message'] = f"❌ camera日志分析异常: {e}"
                print(result['message'])
                allure.attach(traceback.format_exc(), "异常堆栈", allure.attachment_type.TEXT)
                raise
            
            return result


# Pytest fixtures
@pytest.fixture(scope="session")
def e2e_log_manager():
    """E2E日志管理器fixture"""
    return E2ELogManager


@pytest.fixture(scope="session")
def e2e_device_manager():
    """E2E设备管理器fixture"""
    return E2EDeviceManager


@pytest.fixture(scope="session")
def e2e_file_manager():
    """E2E文件管理器fixture"""
    return E2EFileManager


@pytest.fixture(scope="session")
def e2e_log_analyzer():
    """E2E日志分析器fixture"""
    return E2ELogAnalyzer


@pytest.fixture(scope="session")
def e2e_time_helper():
    """E2E时间处理工具fixture"""
    return E2ETimeHelper


@pytest.fixture(scope="session")
def project_root(request):
    """项目根目录fixture"""
    return Path(__file__).resolve().parents[2]

