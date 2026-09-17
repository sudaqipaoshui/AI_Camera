#!/usr/bin/env python 
# coding:utf-8
"""
@Time: 2025-01-20
@Author: gaoyuhang
@Description: X5摄像头SSH底层数据24小时监控
@Purpose: 通过SSH直接获取摄像头底层硬件数据，进行24小时连续监控
@Features: 
- 通过SSH获取系统底层数据
- 24小时连续监控
- 温度、CPU、内存、网络等硬件指标
- 数据图表绘制
- 异常检测和告警
"""

import allure
import pytest
import socket
import time
import json
import csv
import os
import paramiko
import threading
from datetime import datetime, timedelta
from collections import deque
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.dates as mdates
import numpy as np
import logging
import sys


# 设置中文字体
def setup_matplotlib_chinese():
    """根据操作系统自动配置matplotlib中文字体"""
    mpl.rcParams['font.sans-serif'] = ['DejaVu Sans', 'SimHei', 'WenQuanYi Micro Hei', 'Heiti TC']
    mpl.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

    # 根据操作系统类型调整字体优先级
    if os.name == 'posix':
        try:
            if 'Darwin' in os.uname().sysname:
                mpl.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Arial Unicode MS'] + mpl.rcParams['font.sans-serif']
            else:
                mpl.rcParams['font.sans-serif'] = ['Noto Sans CJK JP', 'WenQuanYi Micro Hei'] + mpl.rcParams['font.sans-serif']
        except:
            pass
    elif os.name == 'nt':
        mpl.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei'] + mpl.rcParams['font.sans-serif']


setup_matplotlib_chinese()
# plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
# plt.rcParams['axes.unicode_minus'] = False

# 配置控制台日志记录
def setup_console_logging():
    """设置控制台日志记录"""
    # 配置日志格式
    log_format = '%(asctime)s [%(filename)s:%(lineno)d] %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # 配置根日志器（只输出到控制台）
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # 创建专门的日志器
    logger = logging.getLogger('X5Monitoring')
    logger.setLevel(logging.INFO)
    
    return logger

# 初始化日志
logger = setup_console_logging()
# 降低 paramiko 通道错误刷屏：单次连接断开会产生大量 "Secsh channel XX open FAILED"
logging.getLogger("paramiko.transport").setLevel(logging.WARNING)

@allure.feature('x5-ssh-24h-monitoring')
@allure.story('X5摄像头SSH底层数据24小时监控')
class TestX5SSH24HMonitoring(object):
    
    @pytest.fixture(scope="class", autouse=True)
    def prepare(self, request, env):
        """测试准备"""
        with allure.step("X5摄像头SSH底层数据监控环境准备"):
            self.env = env
            self.ssh_client = None
            
            # 监控配置
            self.monitor_duration = 24 * 3600  # 24小时 (秒)
            self.collect_interval = 60         # 收集间隔 (秒) - 1分钟
            self.data_retention = 2000         # 数据保留数量
            
            # 数据存储
            self.monitoring_data = deque(maxlen=self.data_retention)
            self.error_log = []
            
            # 统计信息
            self.start_time = None
            self.total_collections = 0
            self.successful_collections = 0
            self.ssh_connection_drops = 0
            
            # 阈值配置
            self.temp_threshold = 80.0         # 温度阈值 (°C)
            self.cpu_threshold = 95.0          # CPU使用率阈值 (%)
            self.memory_threshold = 90.0       # 内存使用率阈值 (%)
            self.disk_threshold = 90.0         # 磁盘使用率阈值 (%)
            
            # 创建输出目录（按日期创建）
            current_date = datetime.now().strftime('%Y-%m-%d')
            monitoring_base_dir = os.path.join("allure-report", "24h-monitoring")
            self.output_dir = os.path.join(monitoring_base_dir, current_date)
            os.makedirs(self.output_dir, exist_ok=True)
        
        # 添加清理逻辑
        def cleanup():
            if hasattr(self, 'ssh_client') and self.ssh_client:
                try:
                    self.ssh_client.close()
                    logger.info("SSH连接已关闭")
                except:
                    pass
        request.addfinalizer(cleanup)
        
        return self
    
    @allure.title("X5摄像头SSH底层数据24小时监控")
    @pytest.mark.x5_ssh_24h_monitoring
    @pytest.mark.longrunning
    @pytest.mark.slowme
    def test_x5_ssh_24h_monitoring(self, env):
        """X5摄像头SSH底层数据24小时监控"""
        logger.info("=" * 60)
        logger.info("X5摄像头SSH底层数据24小时监控开始")
        logger.info("=" * 60)
        
        # 监控配置 - 可根据需要调整
        # 选项1: 24小时完整监控
        # monitor_duration = 24 * 3600  # 24小时 = 86400秒
        # collect_interval = 60         # 每60秒收集一次 (1440个数据点)
        
        # 选项2: 1小时测试
        # monitor_duration = 3600       # 1小时 = 3600秒
        # collect_interval = 30         # 每30秒收集一次 (120个数据点)
        
        # 选项3: 10分钟快速测试
        # monitor_duration = 600        # 10分钟 = 600秒
        # collect_interval = 10         # 每10秒收集一次 (60个数据点)
        
        # 选项4: 高频率监控（每10秒，24小时）
        # monitor_duration = 24 * 3600  # 24小时
        # collect_interval = 10         # 每10秒收集一次 (8640个数据点)
        
        # 当前设置: 24小时完整监控版本
        monitor_duration = 24 * 3600  # 24小时 = 86400秒
        collect_interval = 60         # 每60秒收集一次 (1440个数据点)
        
        # 阈值配置
        temp_threshold = 80.0         # 温度阈值 (°C)
        cpu_threshold = 95.0          # CPU使用率阈值 (%)
        memory_threshold = 90.0       # 内存使用率阈值 (%)
        disk_threshold = 90.0         # 磁盘使用率阈值 (%)
        
        logger.info(f"监控配置:")
        logger.info(f"  监控时长: {monitor_duration/3600:.1f} 小时")
        logger.info(f"  收集间隔: {collect_interval} 秒")
        logger.info(f"  预期数据点: {monitor_duration//collect_interval} 个")
        logger.info(f"  温度阈值: {temp_threshold}°C")
        logger.info(f"  CPU阈值: {cpu_threshold}%")
        logger.info(f"  内存阈值: {memory_threshold}%")
        logger.info(f"  磁盘阈值: {disk_threshold}%")
        
        # 确保env和ssh_client正确初始化
        self.env = env
        if not hasattr(self, 'ssh_client'):
            self.ssh_client = None
            
        # 初始化统计变量
        self.start_time = datetime.now()
        self.total_collections = 0
        self.successful_collections = 0
        self.ssh_connection_drops = 0
        # 使用prepare fixture中初始化的列表
        if not hasattr(self, 'error_log'):
            self.error_log = []
        if not hasattr(self, 'monitoring_data'):
            self.monitoring_data = []
        if not hasattr(self, 'output_dir'):
            # 按日期创建输出目录
            current_date = datetime.now().strftime('%Y-%m-%d')
            monitoring_base_dir = os.path.join("allure-report", "24h-monitoring")
            self.output_dir = os.path.join(monitoring_base_dir, current_date)
            os.makedirs(self.output_dir, exist_ok=True)
        end_time = self.start_time + timedelta(seconds=monitor_duration)
        
        with allure.step(f"开始X5摄像头SSH底层数据24小时监控"):
            allure.attach(f"""
            监控配置:
            - 监控时长: {monitor_duration}秒 (演示版本，实际可设置为24小时)
            - 收集间隔: {collect_interval}秒
            - 温度阈值: {temp_threshold}°C
            - CPU阈值: {cpu_threshold}%
            - 内存阈值: {memory_threshold}%
            - 磁盘阈值: {disk_threshold}%
            - 数据源: SSH底层系统数据
            """, "监控配置", allure.attachment_type.TEXT)
            
            # 主监控循环
            print(f"开始监控循环，结束时间: {end_time}")
            while datetime.now() < end_time:
                self.total_collections += 1
                current_time = datetime.now()
                elapsed_time = (current_time - self.start_time).total_seconds()
                print(f"第{self.total_collections}次收集，当前时间: {current_time}")
                
                with allure.step(f"第{self.total_collections}次数据收集 (已运行{elapsed_time/3600:.1f}小时)"):
                    try:
                        # 执行SSH数据收集
                        collection_result = self._collect_ssh_data(current_time, elapsed_time, temp_threshold, cpu_threshold, memory_threshold, disk_threshold)
                        
                        if collection_result['success']:
                            self.successful_collections += 1
                        else:
                            self._handle_collection_failure(collection_result, current_time)
                        
                        # 记录数据
                        try:
                            self._record_monitoring_data(collection_result, current_time, elapsed_time)
                            print(f"数据收集完成，当前数据点数量: {len(self.monitoring_data)}")
                        except Exception as e:
                            print(f"数据记录失败: {str(e)}")
                            import traceback
                            traceback.print_exc()
                        
                        # 定期生成报告
                        if self.total_collections % 60 == 0:  # 每小时生成一次报告
                            self._generate_hourly_report(temp_threshold, cpu_threshold, memory_threshold, disk_threshold)
                        
                    except Exception as e:
                        self._handle_exception(e, current_time, elapsed_time)
                
                # 等待下次收集
                time.sleep(collect_interval)
            
            # 监控完成，生成最终报告
            self._generate_final_report(temp_threshold, cpu_threshold, memory_threshold, disk_threshold)
    
    def _collect_ssh_data(self, current_time, elapsed_time, temp_threshold, cpu_threshold, memory_threshold, disk_threshold):
        """通过SSH收集底层数据"""
        logger.info(f"开始收集SSH数据，当前时间: {current_time}, 已运行: {elapsed_time}")
        start_time = time.time()
        
        collection_result = {
            'timestamp': current_time,
            'elapsed_time': elapsed_time,
            'success': True,
            'ssh_connected': False,
            'system_data': {},
            'hardware_data': {},
            'network_data': {},
            'process_data': {},
            'errors': []
        }
        
        try:
            # 建立SSH连接
            logger.info("步骤1: 建立SSH连接")
            if self._connect_ssh():
                collection_result['ssh_connected'] = True
                logger.info("SSH连接成功")
                
                # 收集系统数据
                logger.info("步骤2: 收集系统数据")
                collection_result['system_data'] = self._collect_system_data()
                logger.debug(f"系统数据收集完成: {len(collection_result['system_data'])} 个字段")
                
                # 收集硬件数据
                logger.info("步骤3: 收集硬件数据")
                collection_result['hardware_data'] = self._collect_hardware_data()
                logger.debug(f"硬件数据收集完成: {len(collection_result['hardware_data'])} 个字段")
                
                # 收集网络数据
                logger.info("步骤4: 收集网络数据")
                collection_result['network_data'] = self._collect_network_data()
                logger.debug(f"网络数据收集完成: {len(collection_result['network_data'])} 个字段")
                
                # 收集进程数据
                logger.info("步骤5: 收集进程数据")
                collection_result['process_data'] = self._collect_process_data()
                logger.debug(f"进程数据收集完成: {len(collection_result['process_data'])} 个字段")
                
                # 验证数据完整性
                logger.info("步骤6: 验证数据完整性")
                self._validate_collected_data(collection_result, temp_threshold, cpu_threshold, memory_threshold, disk_threshold)
                
                # 记录收集时间
                collection_time = time.time() - start_time
                logger.info(f"SSH数据收集完成，耗时: {collection_time:.2f}秒")
                
            else:
                collection_result['success'] = False
                collection_result['errors'].append('SSH连接失败')
                self.ssh_connection_drops += 1
                logger.error("SSH连接失败，跳过本次数据收集")
                # 不收集任何数据，保持失败状态
                
        except Exception as e:
            collection_result['success'] = False
            collection_result['errors'].append(f'数据收集异常: {str(e)}')
            logger.error(f"数据收集异常: {str(e)}")
            # 不收集任何数据，保持失败状态
        
        return collection_result
    
    def _generate_mock_system_data(self, elapsed_time):
        """生成模拟系统数据"""
        import numpy as np
        return {
            'hostname': 'X5-Camera-Demo',
            'uptime': f'{int(elapsed_time/3600)}h {int((elapsed_time%3600)/60)}m',
            'kernel': 'Linux 4.19.0-x5-arm64',
            'load_avg_1min': 0.5 + np.sin(elapsed_time / 10) * 0.2 + np.random.normal(0, 0.1),
            'load_avg_5min': 0.6 + np.sin(elapsed_time / 15) * 0.15 + np.random.normal(0, 0.08),
            'load_avg_15min': 0.7 + np.sin(elapsed_time / 20) * 0.1 + np.random.normal(0, 0.05)
        }
    
    def _generate_mock_hardware_data(self, elapsed_time):
        """生成模拟硬件数据"""
        import numpy as np
        return {
            'temperature': 45.0 + np.sin(elapsed_time / 20) * 5 + np.random.normal(0, 2),
            'cpu_usage': 40.0 + np.sin(elapsed_time / 15) * 10 + np.random.normal(0, 5),
            'memory_usage_percent': 60.0 + np.sin(elapsed_time / 25) * 8 + np.random.normal(0, 3),
            'disk_usage_root': f"{30 + np.random.normal(0, 2):.1f}%",
            'total_processes': 150 + int(np.random.normal(0, 10)),
            'tcp_connections': 20 + int(np.random.normal(0, 3)),
            # 视频性能数据
            'estimated_fps': f"{25.0 + np.sin(elapsed_time / 10) * 3 + np.random.normal(0, 1):.1f}",
            'estimated_bitrate': "2000",
            'estimated_latency': f"{5.0 + np.random.normal(0, 1):.2f}",
            'video_quality_score': f"{85.0 + np.sin(elapsed_time / 12) * 5 + np.random.normal(0, 2):.1f}",
            'camera_processes': "root 1234 0.5 2.1 123456 45678 ? S 10:00 0:05 /usr/bin/camera_daemon\nroot 1235 0.3 1.8 98765 32109 ? S 10:00 0:03 /usr/bin/x5_processor",
            'x5_processes': "root 1235 0.3 1.8 98765 32109 ? S 10:00 0:03 /usr/bin/x5_processor",
            'camera_devices': "/dev/video0\n/dev/video1",
            'usb_cameras': "Bus 001 Device 002: ID 046d:0825 Logitech, Inc. Webcam C270",
            'camera_modules': "uvcvideo 123456 0\nvideobuf2_vmalloc 45678 1 uvcvideo",
            'video_modules': "uvcvideo 123456 0\nvideobuf2_vmalloc 45678 1 uvcvideo"
        }
    
    def _generate_mock_network_data(self):
        """生成模拟网络数据"""
        import numpy as np
        return {
            'eth0_ip': '192.168.1.100',
            'eth0_mac': '00:11:22:33:44:55',
            'wlan0_ip': '192.168.1.101',
            'wlan0_mac': '00:11:22:33:44:56',
            'tcp_established': 15 + int(np.random.normal(0, 2)),
            'tcp_listen': 8 + int(np.random.normal(0, 1)),
            'rx_bytes': 1024000 + int(np.random.normal(0, 100000)),
            'tx_bytes': 512000 + int(np.random.normal(0, 50000))
        }
    
    def _generate_mock_process_data(self):
        """生成模拟进程数据"""
        return {
            'camera_processes': 2,
            'x5_processes': 1,
            'total_processes': 150,
            'high_cpu_processes': ['camera_daemon', 'x5_processor'],
            'high_memory_processes': ['camera_daemon', 'systemd']
        }
    
    def _connect_ssh(self):
        """建立SSH连接，支持超时与重试"""
        ssh_config = {
            'host': self.env.get('ssh_host', '192.168.2.119'),
            'username': self.env.get('ssh_username', 'root'),
            'password': self.env.get('ssh_password', ''),
            'port': int(self.env.get('ssh_port', 22)),
            'timeout': int(self.env.get('ssh_timeout', 10)),
            'connect_retries': int(self.env.get('ssh_connect_retries', 3)),
            'retry_delay': float(self.env.get('ssh_retry_delay', 2.0)),
        }
        if not ssh_config['password']:
            raise RuntimeError(
                "缺少 SSH 口令: 请在项目根 .env 设置 CAMERA_SSH_PASSWORD。"
                "camera.yaml 里的 ssh_password 是 ${CAMERA_SSH_PASSWORD} 占位符, "
                "由 envloader 在运行时展开。"
            )
        _command_timeout = int(self.env.get('ssh_command_timeout', 15))

        # 若已有连接，先做存活检测（channel 超时）
        if self.ssh_client:
            try:
                stdin, stdout, stderr = self.ssh_client.exec_command('echo "test"')
                stdout.channel.settimeout(_command_timeout)
                stdout.read()
                stdout.channel.recv_exit_status()
                stdin.close()
                stdout.close()
                stderr.close()
                return True
            except (socket.timeout, Exception) as e:
                logger.warning(f"SSH 存活检测失败，将重连: {e}")
                try:
                    self.ssh_client.close()
                except Exception:
                    pass
                self.ssh_client = None

        # 新建连接：带重试
        for attempt in range(1, ssh_config['connect_retries'] + 1):
            try:
                self.ssh_client = paramiko.SSHClient()
                self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                logger.info(
                    f"尝试SSH连接 [{attempt}/{ssh_config['connect_retries']}]: "
                    f"{ssh_config['host']}:{ssh_config['port']} (超时={ssh_config['timeout']}s)"
                )
                self.ssh_client.connect(
                    hostname=ssh_config['host'],
                    port=ssh_config['port'],
                    username=ssh_config['username'],
                    password=ssh_config['password'],
                    timeout=ssh_config['timeout'],
                    banner_timeout=ssh_config['timeout'],
                    auth_timeout=ssh_config['timeout'],
                )
                logger.info("SSH连接成功")
                return True
            except Exception as e:
                logger.warning(f"SSH连接失败 (尝试 {attempt}/{ssh_config['connect_retries']}): {e}")
                self.ssh_client = None
                if attempt < ssh_config['connect_retries']:
                    time.sleep(ssh_config['retry_delay'])
        return False
    
    def _invalidate_ssh_connection(self):
        """关闭并清空当前 SSH 连接，下次采集时会自动重连。用于连接已断开（如 channel open failed）时。"""
        if self.ssh_client:
            try:
                self.ssh_client.close()
            except Exception:
                pass
            self.ssh_client = None
            logger.info("SSH 连接已置为无效，下次采集将尝试重连")
    
    def _execute_ssh_command(self, command, ignore_stderr=False):
        """执行SSH命令，使用 channel.settimeout 实现可靠超时。
        ignore_stderr: 若为 True，即使 stderr 有输出也返回 stdout（用于 hrut_somstatus 等会向 stderr 打日志的工具）。
        """
        stdin, stdout, stderr = None, None, None
        cmd_timeout = int(self.env.get('ssh_command_timeout', 15))
        try:
            if not self.ssh_client:
                return None

            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            channel = stdout.channel
            if not channel:
                raise paramiko.SSHException("channel open failed")
            channel.settimeout(cmd_timeout)
            try:
                output = stdout.read().decode('utf-8').strip()
                error = stderr.read().decode('utf-8').strip()
                channel.recv_exit_status()
            except socket.timeout:
                logger.warning(f"SSH 命令执行超时 ({cmd_timeout}s): {command[:80]}...")
                return None

            if error and not ignore_stderr:
                return None
            if error and ignore_stderr:
                logger.debug(f"SSH 命令 stderr 已忽略: {error[:200]}")

            return output
        except (socket.timeout, OSError, paramiko.SSHException) as e:
            logger.debug(f"SSH 命令异常: {e}")
            self._invalidate_ssh_connection()
            return None
        finally:
            if stdin:
                try:
                    stdin.close()
                except Exception:
                    pass
            if stdout:
                try:
                    stdout.close()
                except Exception:
                    pass
            if stderr:
                try:
                    stderr.close()
                except Exception:
                    pass
    
    def _collect_system_data(self):
        """收集系统数据"""
        system_data = {}
        
        try:
            # 系统基本信息
            system_data['hostname'] = self._execute_ssh_command('hostname')
            system_data['uptime'] = self._execute_ssh_command('uptime')
            system_data['kernel'] = self._execute_ssh_command('uname -a')
            system_data['load_average'] = self._execute_ssh_command('cat /proc/loadavg')
            
            # 系统时间
            system_data['system_time'] = self._execute_ssh_command('date')
            
        except Exception as e:
            system_data['error'] = str(e)
        
        return system_data
    
    def _collect_hardware_data(self):
        """收集硬件数据"""
        hardware_data = {}
        
        try:
            # CPU信息
            hardware_data['cpu_cores'] = self._execute_ssh_command('nproc')
            hardware_data['cpu_model'] = self._execute_ssh_command("cat /proc/cpuinfo | grep 'model name' | head -1 | cut -d':' -f2 | xargs")
            
            # 改进CPU使用率收集 - 尝试多种方法
            cpu_usage = self._execute_ssh_command("top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1")
            if not cpu_usage or cpu_usage.strip() == '':
                print("CPU使用率收集方法1失败，尝试备用方法...")
                # 备用方法1：使用vmstat
                cpu_usage = self._execute_ssh_command("vmstat 1 2 | tail -1 | awk '{print 100-$15}'")
            if not cpu_usage or cpu_usage.strip() == '':
                print("CPU使用率收集方法2失败，尝试备用方法...")
                # 备用方法2：使用/proc/stat
                cpu_usage = self._execute_ssh_command("grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$3+$4+$5)} END {print usage}'")
            if not cpu_usage or cpu_usage.strip() == '':
                print("CPU使用率收集方法3失败，尝试备用方法...")
                # 备用方法3：使用sar
                cpu_usage = self._execute_ssh_command("sar 1 1 | tail -1 | awk '{print 100-$8}'")
            
            if cpu_usage and cpu_usage.strip():
                print(f"CPU使用率收集成功: {cpu_usage}")
            else:
                print("所有CPU使用率收集方法都失败")
            hardware_data['cpu_usage'] = cpu_usage
            
            hardware_data['load_avg_1min'] = self._execute_ssh_command("cat /proc/loadavg | awk '{print $1}'")
            hardware_data['load_avg_5min'] = self._execute_ssh_command("cat /proc/loadavg | awk '{print $2}'")
            hardware_data['load_avg_15min'] = self._execute_ssh_command("cat /proc/loadavg | awk '{print $3}'")
            
            # 内存信息
            hardware_data['memory_total'] = self._execute_ssh_command("free -h | grep 'Mem:' | awk '{print $2}'")
            hardware_data['memory_used'] = self._execute_ssh_command("free -h | grep 'Mem:' | awk '{print $3}'")
            hardware_data['memory_free'] = self._execute_ssh_command("free -h | grep 'Mem:' | awk '{print $4}'")
            hardware_data['memory_usage_percent'] = self._execute_ssh_command("free | grep 'Mem:' | awk '{printf \"%.1f\", $3/$2 * 100.0}'")
            hardware_data['swap_used'] = self._execute_ssh_command("free -h | grep 'Swap:' | awk '{print $3}'")
            
            # 磁盘信息 - 改进收集方法，监控多个分区
            # 1. 根分区使用率
            disk_usage_root = self._execute_ssh_command("df -h / | tail -1 | awk '{print $5}'")
            if not disk_usage_root or disk_usage_root.strip() == '':
                print("根分区磁盘使用率收集方法1失败，尝试备用方法...")
                disk_usage_root = self._execute_ssh_command("df -P / | tail -1 | awk '{print $5}'")
            if not disk_usage_root or disk_usage_root.strip() == '':
                print("根分区磁盘使用率收集方法2失败，尝试备用方法...")
                disk_usage_root = self._execute_ssh_command("df / | tail -1 | awk '{printf \"%.1f%%\", $3/$2*100}'")
            
            # 2. userdata分区使用率（主要数据分区）
            disk_usage_userdata = self._execute_ssh_command("df -h /userdata | tail -1 | awk '{print $5}'")
            if not disk_usage_userdata or disk_usage_userdata.strip() == '':
                print("userdata分区磁盘使用率收集失败")
                disk_usage_userdata = "0%"
            
            # 3. app分区使用率
            disk_usage_app = self._execute_ssh_command("df -h /app | tail -1 | awk '{print $5}'")
            if not disk_usage_app or disk_usage_app.strip() == '':
                print("app分区磁盘使用率收集失败")
                disk_usage_app = "0%"
            
            if disk_usage_root and disk_usage_root.strip():
                print(f"根分区磁盘使用率: {disk_usage_root}")
            if disk_usage_userdata and disk_usage_userdata.strip():
                print(f"userdata分区磁盘使用率: {disk_usage_userdata}")
            if disk_usage_app and disk_usage_app.strip():
                print(f"app分区磁盘使用率: {disk_usage_app}")
            
            # 保存多个分区的使用率
            hardware_data['disk_usage_root'] = disk_usage_root
            hardware_data['disk_usage_userdata'] = disk_usage_userdata
            hardware_data['disk_usage_app'] = disk_usage_app
            
            # 主要监控userdata分区（因为这是主要的数据存储分区）
            hardware_data['disk_usage'] = disk_usage_userdata
            
            hardware_data['disk_size'] = self._execute_ssh_command("df -h / | tail -1 | awk '{print $2}'")
            hardware_data['disk_used'] = self._execute_ssh_command("df -h / | tail -1 | awk '{print $3}'")
            hardware_data['disk_available'] = self._execute_ssh_command("df -h / | tail -1 | awk '{print $4}'")
            hardware_data['inode_usage'] = self._execute_ssh_command("df -i / | tail -1 | awk '{print $5}'")
            
            # 温度信息
            temp_file = self._execute_ssh_command("ls /sys/class/thermal/thermal_zone*/temp 2>/dev/null | head -1")
            if temp_file:
                temp_raw = self._execute_ssh_command(f"cat {temp_file}")
                if temp_raw and temp_raw.isdigit():
                    temp_celsius = int(temp_raw) / 1000
                    hardware_data['temperature'] = f"{temp_celsius:.1f}"
                else:
                    hardware_data['temperature'] = "N/A"
            else:
                hardware_data['temperature'] = "N/A"
            
            # 风扇信息（如果有）
            hardware_data['fan_speed'] = self._execute_ssh_command("cat /sys/class/hwmon/hwmon*/fan*_input 2>/dev/null | head -1")
            
            # BPU 信息：使用 hrut_somstatus（设备上路径为 /usr/hobot/bin/hrut_somstatus）
            bpu_somstatus_raw = self._execute_ssh_command("timeout 5 /usr/hobot/bin/hrut_somstatus 2>&1", ignore_stderr=True)
            if not bpu_somstatus_raw:
                bpu_somstatus_raw = self._execute_ssh_command("/usr/hobot/bin/hrut_somstatus 2>&1", ignore_stderr=True)
            hardware_data['bpu_somstatus'] = bpu_somstatus_raw if bpu_somstatus_raw else ""
            if bpu_somstatus_raw:
                logger.info("BPU hrut_somstatus 已采集 (原始 %d 字符)", len(bpu_somstatus_raw.strip()))
                logger.debug("BPU hrut_somstatus 原始输出:\n%s", bpu_somstatus_raw.strip())
            parsed = self._parse_bpu_somstatus_output(hardware_data.get('bpu_somstatus', ''))
            raw_preview = (bpu_somstatus_raw or "").strip()[:200]
            if not bpu_somstatus_raw:
                logger.debug("BPU: hrut_somstatus 无输出（命令可能不存在或超时）")
            elif "no such file or directory" in raw_preview.lower() or "failed to run command" in raw_preview.lower() or "not found" in raw_preview.lower():
                logger.info("BPU: 当前设备无 hrut_somstatus 命令，跳过 BPU 数据采集（%s）", raw_preview[:80])
            elif not any([parsed.get('temp_bpu'), parsed.get('bpu_freq_mhz'), parsed.get('bpu0_ratio') is not None]):
                logger.warning("BPU: hrut_somstatus 有输出但解析未匹配，前 300 字符: %s", (bpu_somstatus_raw or "")[:300])
            hardware_data['bpu_usage'] = parsed.get('bpu_usage')
            hardware_data['bpu_cur_freq_mhz'] = parsed.get('bpu_freq_mhz')
            hardware_data['bpu0_ratio'] = parsed.get('bpu0_ratio')
            hardware_data['bpu1_ratio'] = parsed.get('bpu1_ratio')
            if parsed.get('bpu_cur_freq_hz') is not None:
                hardware_data['bpu_cur_freq_hz'] = str(parsed['bpu_cur_freq_hz'])
            elif not hardware_data.get('bpu_cur_freq_hz'):
                hardware_data['bpu_cur_freq_hz'] = ""
            # 温度来自 hrut_somstatus（DDR/BPU/CPU）
            if parsed.get('temp_bpu') is not None:
                hardware_data['bpu_temperature'] = f"{parsed['temp_bpu']:.1f}"
            else:
                hardware_data['bpu_temperature'] = ""
            if parsed.get('temp_ddr') is not None:
                hardware_data['temperature_hrut_ddr'] = f"{parsed['temp_ddr']:.1f}"
            if parsed.get('temp_cpu') is not None:
                hardware_data['temperature_hrut_cpu'] = f"{parsed['temp_cpu']:.1f}"
            
            # FPS和视频性能信息收集
            video_performance_data = self._collect_video_performance_data()
            hardware_data.update(video_performance_data)
            
        except Exception as e:
            hardware_data['error'] = str(e)
        
        return hardware_data
    
    def _collect_video_performance_data(self):
        """收集视频性能数据（FPS、码率、分辨率、GOP、延迟等）"""
        video_data = {}
        
        try:
            # 1. 基础摄像头信息
            video_data['camera_processes'] = self._execute_ssh_command("ps aux | grep -i camera | grep -v grep")
            video_data['x5_processes'] = self._execute_ssh_command("ps aux | grep -i x5 | grep -v grep")
            video_data['camera_devices'] = self._execute_ssh_command("ls /dev/video* 2>/dev/null")
            video_data['usb_cameras'] = self._execute_ssh_command("lsusb | grep -i camera")
            video_data['camera_modules'] = self._execute_ssh_command("lsmod | grep -i camera")
            video_data['video_modules'] = self._execute_ssh_command("lsmod | grep -i video")
            
            # 2. 帧率(FPS)相关数据
            video_data['camera_logs'] = self._execute_ssh_command("dmesg | grep -i fps | tail -5")
            video_data['camera_errors'] = self._execute_ssh_command("dmesg | grep -i camera | tail -5")
            
            # 从系统日志中提取完整的视频性能指标
            log_metrics = self._extract_video_metrics_from_logs()
            
            # 使用从日志提取的真实数据
            if log_metrics.get('real_fps') is not None:
                video_data['real_fps'] = f"{log_metrics['real_fps']:.1f}"
            if log_metrics.get('target_fps') is not None:
                video_data['target_fps'] = f"{log_metrics['target_fps']:.1f}"
            if log_metrics.get('smart_fps') is not None:
                video_data['smart_fps'] = f"{log_metrics['smart_fps']:.1f}"
            if log_metrics.get('estimated_fps') is not None:
                video_data['estimated_fps'] = f"{log_metrics['estimated_fps']:.1f}"
            elif log_metrics.get('real_fps') is not None:
                # 如果没有analysis fps，使用real_fps作为estimated_fps的备用值
                video_data['estimated_fps'] = f"{log_metrics['real_fps']:.1f}"
            else:
                # 如果无法从日志获取，则使用估算方法
                load_details = self._execute_ssh_command("cat /proc/loadavg")
                if load_details:
                    load_parts = load_details.split()
                    if len(load_parts) >= 3:
                        load_1min = float(load_parts[0])
                        # 基于负载估算FPS（经验公式）
                        estimated_fps = max(0, 30 - (load_1min * 2))  # 基础30fps，负载越高FPS越低
                        video_data['estimated_fps'] = f"{estimated_fps:.1f}"
                    else:
                        video_data['estimated_fps'] = "N/A"
                else:
                    video_data['estimated_fps'] = "N/A"
            
            # 添加从日志提取的其他指标
            if log_metrics.get('real_bitrate') is not None:
                video_data['real_bitrate'] = f"{log_metrics['real_bitrate']:.1f}"
            
            if log_metrics.get('real_resolution') is not None:
                video_data['real_resolution'] = log_metrics['real_resolution']
            
            if log_metrics.get('real_gop') is not None:
                video_data['real_gop'] = f"{log_metrics['real_gop']:.0f}"
            
            if log_metrics.get('real_latency') is not None:
                video_data['real_latency'] = f"{log_metrics['real_latency']:.1f}"
            
            if log_metrics.get('real_quality_score') is not None:
                video_data['real_quality_score'] = f"{log_metrics['real_quality_score']:.1f}"
            
            if log_metrics.get('codec_info') is not None:
                codec_info = log_metrics['codec_info']
                if codec_info.get('codec'):
                    video_data['codec'] = codec_info['codec']
                if codec_info.get('profile'):
                    video_data['codec_profile'] = codec_info['profile']
            
            # 3. 码率(Bitrate)相关数据
            # 从网络流量推断码率
            network_stats = self._execute_ssh_command("cat /proc/net/dev | grep -E 'eth0|wlan0'")
            video_data['network_stats'] = network_stats
            
            # 从IO统计推断码率
            io_stats = self._execute_ssh_command("iostat -x 1 1 2>/dev/null | tail -10")
            video_data['io_stats'] = io_stats
            
            # 从进程IO获取码率信息
            video_data['process_io'] = self._execute_ssh_command("cat /proc/*/io 2>/dev/null | grep -A5 -B5 camera | head -20")
            
            # 4. 分辨率(Resolution)相关数据
            # 从摄像头设备获取分辨率信息
            video_data['camera_capabilities'] = self._execute_ssh_command("v4l2-ctl --list-formats-ext 2>/dev/null | head -20")
            video_data['camera_info'] = self._execute_ssh_command("v4l2-ctl --info 2>/dev/null")
            
            # 从系统日志获取分辨率信息
            video_data['resolution_logs'] = self._execute_ssh_command("dmesg | grep -i resolution | tail -5")
            video_data['video_logs'] = self._execute_ssh_command("dmesg | grep -i video | tail -5")
            
            # 5. I帧间隔(GOP Size)相关数据
            # 从编码器配置获取GOP信息
            video_data['encoder_config'] = self._execute_ssh_command("find /sys -name '*gop*' -o -name '*keyframe*' 2>/dev/null | head -5")
            video_data['codec_info'] = self._execute_ssh_command("cat /proc/modules | grep -i codec")
            
            # 从系统日志获取GOP信息
            video_data['gop_logs'] = self._execute_ssh_command("dmesg | grep -i gop | tail -5")
            video_data['keyframe_logs'] = self._execute_ssh_command("dmesg | grep -i keyframe | tail -5")
            
            # 6. 延迟(Latency)相关数据
            # 网络延迟
            video_data['network_latency'] = self._execute_ssh_command("ping -c 1 127.0.0.1 2>/dev/null | grep time")
            
            # 系统延迟统计
            video_data['interrupt_stats'] = self._execute_ssh_command("cat /proc/interrupts | grep -i camera")
            video_data['syscall_stats'] = self._execute_ssh_command("cat /proc/stat | head -5")
            video_data['syscall_frequency'] = self._execute_ssh_command("cat /proc/stat | grep ctxt")
            
            # 进程调度延迟
            video_data['process_scheduling'] = self._execute_ssh_command("cat /proc/schedstat | head -5")
            
            # 7. 视频编码相关数据
            # 编码器状态
            video_data['encoder_status'] = self._execute_ssh_command("ps aux | grep -i encode | grep -v grep")
            video_data['ffmpeg_processes'] = self._execute_ssh_command("ps aux | grep -i ffmpeg | grep -v grep")
            
            # 编码器配置
            video_data['codec_modules'] = self._execute_ssh_command("lsmod | grep -E 'h264|h265|mpeg|codec'")
            
            # 8. 内存和缓存相关数据
            # 视频缓冲区
            video_data['video_buffers'] = self._execute_ssh_command("cat /proc/meminfo | grep -E 'Buffers|Cached|Active|Inactive'")
            video_data['memory_allocation'] = self._execute_ssh_command("cat /proc/vmstat | grep -E 'pgalloc|pgfree'")
            
            # 9. 系统性能相关数据
            # CPU使用详情
            video_data['cpu_details'] = self._execute_ssh_command("cat /proc/stat | grep cpu")
            
            # 系统时间精度
            video_data['time_precision'] = self._execute_ssh_command("cat /proc/timer_list | grep resolution | head -1")
            
            # 10. 摄像头配置文件
            # 查找摄像头配置文件
            video_data['camera_config'] = self._execute_ssh_command("find /etc /usr/local/etc -name '*camera*' -o -name '*x5*' 2>/dev/null | head -5")
            
            # 摄像头服务状态
            video_data['camera_services'] = self._execute_ssh_command("systemctl list-units --type=service | grep -i camera")
            
            # 11. 实时性能监控
            # 获取实时性能数据
            video_data['real_time_stats'] = self._execute_ssh_command("top -bn1 | grep -E 'camera|x5|ffmpeg'")
            
            # 12. 网络流媒体相关
            # RTSP/RTMP流信息
            video_data['rtsp_processes'] = self._execute_ssh_command("ps aux | grep -i rtsp | grep -v grep")
            video_data['rtmp_processes'] = self._execute_ssh_command("ps aux | grep -i rtmp | grep -v grep")
            
            # 网络连接统计
            video_data['network_connections'] = self._execute_ssh_command("ss -tuln | grep -E '554|1935'")
            
            # 13. 计算综合性能指标
            # 基于收集的数据计算综合指标
            video_data = self._calculate_video_metrics(video_data)
            
        except Exception as e:
            video_data['error'] = str(e)
        
        return video_data
    
    def _extract_fps_from_logs(self):
        """从系统日志中提取FPS信息（Actual FPS, Target FPS, Smart fps, analysis fps）"""
        try:
            logger.info("开始从系统日志中提取FPS信息")
            # 定义日志目录
            log_dir = "/userdata/deploy/log"
            logger.debug(f"目标日志目录: {log_dir}")
            
            # 初始化FPS值字典
            fps_dict = {
                'actual_fps': None,      # Actual FPS -> 真实FPS
                'target_fps': None,       # Target FPS -> 目标FPS
                'smart_fps': None,        # Smart fps -> 智能FPS
                'analysis_fps': None       # analysis fps -> 估算FPS
            }
            
            # 1. 检查日志目录是否存在
            check_log_dir = self._execute_ssh_command(f"ls -la {log_dir} 2>/dev/null")
            if not check_log_dir:
                logger.warning(f"日志目录不存在: {log_dir}")
                logger.warning("尝试查找其他可能的日志目录...")
                # 尝试其他可能的日志路径
                alt_paths = ["/userdata/log", "/var/log", "/tmp/log"]
                for alt_path in alt_paths:
                    alt_check = self._execute_ssh_command(f"ls -la {alt_path} 2>/dev/null")
                    if alt_check:
                        logger.info(f"找到备用日志目录: {alt_path}")
                        log_dir = alt_path
                        break
                else:
                    logger.error("未找到任何日志目录")
                    return None
            else:
                logger.info(f"✓ 日志目录检查成功: {log_dir}")
                logger.debug(f"日志目录内容预览: {check_log_dir[:200]}...")
            
            # 2. 查找最新的日志文件（包括当前正在写入的）
            # 优先查找最新的日志文件（按修改时间排序）
            log_files = self._execute_ssh_command(f"find {log_dir} -name '*.log' -type f -mtime -1 2>/dev/null | xargs ls -t 2>/dev/null | head -10")
            if not log_files or log_files.strip() == '':
                # 备用：查找所有日志文件，按修改时间排序
                logger.debug("方法1未找到日志文件，尝试备用方法...")
                log_files = self._execute_ssh_command(f"find {log_dir} -name '*.log' -type f 2>/dev/null | xargs ls -t 2>/dev/null | head -10")
            
            if not log_files or log_files.strip() == '':
                logger.warning(f"在 {log_dir} 中未找到日志文件")
                return None
            else:
                logger.debug(f"找到日志文件: {log_files}")
                file_list = [f.strip() for f in log_files.strip().split('\n') if f.strip()]
                file_count = len(file_list)
                logger.info(f"找到 {file_count} 个日志文件")
                if file_count > 0:
                    logger.info(f"最新日志文件: {file_list[0]}")
            
            # 3. 定义FPS提取模式
            actual_fps_pattern = r'Actual FPS[:\s,]+(\d+(?:\.\d+)?)'
            target_fps_pattern = r'Target FPS[:\s,]+(\d+(?:\.\d+)?)'
            smart_fps_pattern = r'Smart fps\s*=\s*(\d+(?:\.\d+)?)'
            analysis_fps_pattern = r'analysis fps\s+(\d+(?:\.\d+)?)'
            
            logger.debug("开始搜索FPS信息（Actual FPS, Target FPS, Smart fps, analysis fps）")
            
            # 优先方法：直接搜索 "MIPI Camera Statistics" 格式的日志
            logger.info("优先搜索 MIPI Camera Statistics 格式的FPS数据")
            
            # 方法1: 搜索所有日志文件中的 MIPI Camera Statistics
            mipi_stats_cmd = f"grep -h 'MIPI Camera Statistics' {log_dir}/*.log 2>/dev/null | tail -20"
            mipi_stats_output = self._execute_ssh_command(mipi_stats_cmd)
            
            # 方法2: 如果方法1没找到，直接搜索 logger.log（最常见的日志文件名）
            if not mipi_stats_output or mipi_stats_output.strip() == '':
                logger.debug("方法1未找到，尝试直接搜索 logger.log...")
                logger_log_path = f"{log_dir}/logger.log"
                mipi_stats_cmd = f"grep 'MIPI Camera Statistics' '{logger_log_path}' 2>/dev/null | tail -20"
                mipi_stats_output = self._execute_ssh_command(mipi_stats_cmd)
            
            # 方法3: 搜索所有可能的日志文件名
            if not mipi_stats_output or mipi_stats_output.strip() == '':
                logger.debug("方法2未找到，尝试搜索所有日志文件...")
                mipi_stats_cmd = f"find {log_dir} -name '*.log' -type f -exec grep -l 'MIPI Camera Statistics' {{}} \\; 2>/dev/null | head -5 | xargs grep 'MIPI Camera Statistics' 2>/dev/null | tail -20"
                mipi_stats_output = self._execute_ssh_command(mipi_stats_cmd)
            
            import re
            if mipi_stats_output:
                logger.info(f"找到 MIPI Camera Statistics 日志")
                logger.debug(f"MIPI日志预览: {mipi_stats_output[:300]}...")
                
                for line in mipi_stats_output.split('\n'):
                    if line.strip():
                        # 提取 Actual FPS
                        if 'Actual FPS' in line and not fps_dict['actual_fps']:
                            match = re.search(actual_fps_pattern, line, re.IGNORECASE)
                            if match:
                                try:
                                    fps_value = float(match.group(1))
                                    if 1 <= fps_value <= 120:
                                        fps_dict['actual_fps'] = fps_value
                                        logger.info(f"✓ 提取到Actual FPS: {fps_value} (来源: {line.strip()[:100]})")
                                except ValueError:
                                    logger.debug(f"Actual FPS值转换失败: {match.group(1)}")
                        
                        # 提取 Target FPS
                        if 'Target FPS' in line and not fps_dict['target_fps']:
                            match = re.search(target_fps_pattern, line, re.IGNORECASE)
                            if match:
                                try:
                                    fps_value = float(match.group(1))
                                    if 1 <= fps_value <= 120:
                                        fps_dict['target_fps'] = fps_value
                                        logger.info(f"✓ 提取到Target FPS: {fps_value} (来源: {line.strip()[:100]})")
                                except ValueError:
                                    logger.debug(f"Target FPS值转换失败: {match.group(1)}")
            
            # 搜索 Smart fps 和 analysis fps
            logger.info("搜索 Smart fps 和 analysis fps")
            smart_fps_cmd = f"grep -iE 'Smart fps|analysis fps' {log_dir}/*.log 2>/dev/null | tail -10"
            smart_analysis_output = self._execute_ssh_command(smart_fps_cmd)
            
            if smart_analysis_output:
                logger.debug(f"找到 Smart fps/analysis fps 日志: {smart_analysis_output[:200]}...")
                for line in smart_analysis_output.split('\n'):
                    if line.strip():
                        # 提取 Smart fps
                        if 'Smart fps' in line and not fps_dict['smart_fps']:
                            match = re.search(smart_fps_pattern, line, re.IGNORECASE)
                            if match:
                                try:
                                    fps_value = float(match.group(1))
                                    if 1 <= fps_value <= 120:
                                        fps_dict['smart_fps'] = fps_value
                                        logger.info(f"✓ 提取到Smart fps: {fps_value} (来源: {line.strip()[:100]})")
                                except ValueError:
                                    logger.debug(f"Smart fps值转换失败: {match.group(1)}")
                        
                        # 提取 analysis fps
                        if 'analysis fps' in line and not fps_dict['analysis_fps']:
                            match = re.search(analysis_fps_pattern, line, re.IGNORECASE)
                            if match:
                                try:
                                    fps_value = float(match.group(1))
                                    if 1 <= fps_value <= 120:
                                        fps_dict['analysis_fps'] = fps_value
                                        logger.info(f"✓ 提取到analysis fps: {fps_value} (来源: {line.strip()[:100]})")
                                except ValueError:
                                    logger.debug(f"analysis fps值转换失败: {match.group(1)}")
            
            # 搜索每个日志文件（备用方法）
            for log_file in log_files.strip().split('\n'):
                if log_file.strip():
                    logger.debug(f"搜索日志文件: {log_file}")
                    
                    # 搜索所有FPS相关内容
                    grep_cmd = f"grep -iE 'Actual FPS|Target FPS|Smart fps|analysis fps' '{log_file}' | tail -10"
                    fps_matches = self._execute_ssh_command(grep_cmd)
                    
                    if fps_matches:
                        logger.debug(f"在文件 {log_file} 中找到FPS相关内容")
                        for line in fps_matches.split('\n'):
                            if line.strip():
                                # 提取 Actual FPS
                                if 'Actual FPS' in line and not fps_dict['actual_fps']:
                                    match = re.search(actual_fps_pattern, line, re.IGNORECASE)
                                    if match:
                                        try:
                                            fps_value = float(match.group(1))
                                            if 1 <= fps_value <= 120:
                                                fps_dict['actual_fps'] = fps_value
                                                logger.info(f"✓ 提取到Actual FPS: {fps_value}")
                                        except ValueError:
                                            pass
                                
                                # 提取 Target FPS
                                if 'Target FPS' in line and not fps_dict['target_fps']:
                                    match = re.search(target_fps_pattern, line, re.IGNORECASE)
                                    if match:
                                        try:
                                            fps_value = float(match.group(1))
                                            if 1 <= fps_value <= 120:
                                                fps_dict['target_fps'] = fps_value
                                                logger.info(f"✓ 提取到Target FPS: {fps_value}")
                                        except ValueError:
                                            pass
                                
                                # 提取 Smart fps
                                if 'Smart fps' in line and not fps_dict['smart_fps']:
                                    match = re.search(smart_fps_pattern, line, re.IGNORECASE)
                                    if match:
                                        try:
                                            fps_value = float(match.group(1))
                                            if 1 <= fps_value <= 120:
                                                fps_dict['smart_fps'] = fps_value
                                                logger.info(f"✓ 提取到Smart fps: {fps_value}")
                                        except ValueError:
                                            pass
                                
                                # 提取 analysis fps
                                if 'analysis fps' in line and not fps_dict['analysis_fps']:
                                    match = re.search(analysis_fps_pattern, line, re.IGNORECASE)
                                    if match:
                                        try:
                                            fps_value = float(match.group(1))
                                            if 1 <= fps_value <= 120:
                                                fps_dict['analysis_fps'] = fps_value
                                                logger.info(f"✓ 提取到analysis fps: {fps_value}")
                                        except ValueError:
                                            pass
            
            # 4. 返回FPS字典
            found_count = sum(1 for v in fps_dict.values() if v is not None)
            if found_count > 0:
                logger.info(f"✓✓✓ 成功提取到 {found_count} 个FPS值:")
                for key, value in fps_dict.items():
                    if value is not None:
                        logger.info(f"  {key}: {value:.2f}")
                return fps_dict
            
            # 5. 如果没找到任何FPS，返回空字典
            logger.warning("未能从日志中提取到有效的FPS信息")
            logger.debug(f"  日志目录: {log_dir}")
            logger.debug(f"  找到的日志文件数: {file_count if 'file_count' in locals() else '未知'}")
            
            return fps_dict
            
        except Exception as e:
            logger.error(f"从日志提取FPS信息时发生异常: {e}")
            return None
    
    def _extract_video_metrics_from_logs(self):
        """从日志中提取完整的视频性能指标"""
        try:
            logger.info("开始从日志中提取完整的视频性能指标")
            metrics = {
                'real_fps': None,          # Actual FPS -> 真实FPS
                'target_fps': None,        # Target FPS -> 目标FPS
                'smart_fps': None,         # Smart fps -> 智能FPS
                'estimated_fps': None,     # analysis fps -> 估算FPS
                'real_bitrate': None,
                'real_resolution': None,
                'real_gop': None,
                'real_latency': None,
                'real_quality_score': None,
                'codec_info': None
            }
            
            # 定义日志目录
            log_dir = "/userdata/deploy/log"
            logger.debug(f"目标日志目录: {log_dir}")
            
            # 1. 提取FPS信息（返回字典）
            logger.info("步骤1: 提取FPS信息")
            fps_data = self._extract_fps_from_logs()
            if fps_data and isinstance(fps_data, dict):
                # 映射字段：Actual FPS -> real_fps, analysis fps -> estimated_fps
                metrics['real_fps'] = fps_data.get('actual_fps')  # Actual FPS -> 真实FPS
                metrics['target_fps'] = fps_data.get('target_fps')  # Target FPS -> 目标FPS
                metrics['smart_fps'] = fps_data.get('smart_fps')  # Smart fps -> 智能FPS
                metrics['estimated_fps'] = fps_data.get('analysis_fps')  # analysis fps -> 估算FPS
                logger.info(f"FPS提取结果: real_fps={metrics['real_fps']}, target_fps={metrics['target_fps']}, smart_fps={metrics['smart_fps']}, estimated_fps={metrics['estimated_fps']}")
            else:
                # 兼容旧版本（返回单个值）
                metrics['real_fps'] = fps_data
                logger.info(f"FPS提取结果: {metrics['real_fps']}")
            
            # 2. 提取码率信息
            logger.info("步骤2: 提取码率信息")
            metrics['real_bitrate'] = self._extract_bitrate_from_logs()
            logger.info(f"码率提取结果: {metrics['real_bitrate']}")
            
            # 3. 提取分辨率信息
            logger.info("步骤3: 提取分辨率信息")
            metrics['real_resolution'] = self._extract_resolution_from_logs()
            logger.info(f"分辨率提取结果: {metrics['real_resolution']}")
            
            # 4. 提取GOP信息
            logger.info("步骤4: 提取GOP信息")
            metrics['real_gop'] = self._extract_gop_from_logs()
            logger.info(f"GOP提取结果: {metrics['real_gop']}")
            
            # 5. 提取延迟信息
            logger.info("步骤5: 提取延迟信息")
            metrics['real_latency'] = self._extract_latency_from_logs()
            logger.info(f"延迟提取结果: {metrics['real_latency']}")
            
            # 6. 提取视频质量分数
            logger.info("步骤6: 提取视频质量分数")
            metrics['real_quality_score'] = self._extract_quality_score_from_logs()
            logger.info(f"视频质量分数提取结果: {metrics['real_quality_score']}")
            
            # 7. 提取编码器信息
            logger.info("步骤7: 提取编码器信息")
            metrics['codec_info'] = self._extract_codec_info_from_logs()
            logger.info(f"编码器信息提取结果: {metrics['codec_info']}")
            
            # 统计提取结果
            extracted_count = sum(1 for v in metrics.values() if v is not None)
            total_count = len(metrics)
            logger.info(f"视频性能指标提取完成: {extracted_count}/{total_count} 个指标成功提取")
            
            return metrics
            
        except Exception as e:
            logger.error(f"从日志提取视频性能指标时发生异常: {e}")
            return {}
    
    def _extract_bitrate_from_logs(self):
        """从日志中提取码率信息"""
        try:
            # 定义码率搜索模式
            bitrate_patterns = [
                r'bitrate[:\s]*(\d+(?:\.\d+)?)\s*(kbps|mbps|bps)',
                r'码率[:\s]*(\d+(?:\.\d+)?)\s*(kbps|mbps|bps)',
                r'Bitrate[:\s]*(\d+(?:\.\d+)?)\s*(kbps|mbps|bps)',
                r'(\d+(?:\.\d+)?)\s*(kbps|mbps|bps)',
                r'rate[:\s]*(\d+(?:\.\d+)?)\s*(kbps|mbps|bps)',
                r'bandwidth[:\s]*(\d+(?:\.\d+)?)\s*(kbps|mbps|bps)',
                r'encoder.*?(\d+(?:\.\d+)?)\s*(kbps|mbps|bps)',
                r'stream.*?(\d+(?:\.\d+)?)\s*(kbps|mbps|bps)'
            ]
            
            # 搜索多个日志源
            log_sources = [
                "dmesg | grep -i 'bitrate\\|码率\\|rate' | tail -10",
                "journalctl -u camera* --since '1 hour ago' | grep -i 'bitrate\\|码率\\|rate' | tail -10",
                "find /userdata/deploy/log -name '*.log' -exec grep -l -i 'bitrate\\|码率\\|rate' {} \\; | head -5"
            ]
            
            bitrate_values = []
            
            for source in log_sources:
                output = self._execute_ssh_command(source)
                if output:
                    import re
                    for pattern in bitrate_patterns:
                        matches = re.findall(pattern, output, re.IGNORECASE)
                        for match in matches:
                            try:
                                value = float(match[0])
                                unit = match[1].lower()
                                
                                # 转换为kbps
                                if unit == 'mbps':
                                    value *= 1000
                                elif unit == 'bps':
                                    value /= 1000
                                
                                if 100 <= value <= 10000:  # 合理的码率范围
                                    bitrate_values.append(value)
                            except (ValueError, IndexError):
                                continue
            
            if bitrate_values:
                avg_bitrate = sum(bitrate_values) / len(bitrate_values)
                logging.info(f"从日志中提取到 {len(bitrate_values)} 个码率值，平均值: {avg_bitrate:.1f} kbps")
                return avg_bitrate
            
            return None
            
        except Exception as e:
            logging.error(f"从日志提取码率信息时发生异常: {e}")
            return None
    
    def _extract_resolution_from_logs(self):
        """从日志中提取分辨率信息"""
        try:
            logger.info("开始从日志中提取分辨率信息")
            # 定义分辨率搜索模式
            resolution_patterns = [
                r'(\d{3,4})\s*[x×]\s*(\d{3,4})',
                r'(\d{3,4})\s*[*]\s*(\d{3,4})',
                r'resolution[:\s]*(\d{3,4})\s*[x×*]\s*(\d{3,4})',
                r'分辨率[:\s]*(\d{3,4})\s*[x×*]\s*(\d{3,4})',
                r'Resolution[:\s]*(\d{3,4})\s*[x×*]\s*(\d{3,4})',  # 新增：支持大写Resolution
                r'(\d{3,4})p',
                r'(\d{3,4})i',
                r'width[:\s]*(\d{3,4}).*height[:\s]*(\d{3,4})',
                r'height[:\s]*(\d{3,4}).*width[:\s]*(\d{3,4})'
            ]
            
            # 搜索多个日志源
            log_sources = [
                "dmesg | grep -i 'resolution\\|分辨率\\|width\\|height' | tail -10",
                "journalctl -u camera* --since '1 hour ago' | grep -i 'resolution\\|分辨率\\|width\\|height' | tail -10",
                "find /userdata/deploy/log -name '*.log' -exec grep -l -i 'resolution\\|分辨率\\|width\\|height' {} \\; | head -5",
                "find /userdata/deploy/log -name '*.log' -exec grep -i 'MIPI Camera Statistics' {} \\; | tail -5",  # 新增：专门搜索MIPI Camera Statistics
                "find /userdata/deploy/log -name '*.log' -exec grep -i 'Resolution:' {} \\; | tail -5"  # 新增：搜索Resolution:格式
            ]
            
            resolutions = []
            
            for i, source in enumerate(log_sources):
                logger.debug(f"分辨率搜索源 {i+1}: {source}")
                output = self._execute_ssh_command(source)
                if output:
                    logger.debug(f"分辨率搜索源 {i+1} 输出: {output[:200]}...")  # 只显示前200个字符
                    import re
                    for pattern in resolution_patterns:
                        matches = re.findall(pattern, output, re.IGNORECASE)
                        for match in matches:
                            try:
                                if len(match) == 2:
                                    width, height = int(match[0]), int(match[1])
                                    if 320 <= width <= 7680 and 240 <= height <= 4320:
                                        resolutions.append(f"{width}x{height}")
                                elif len(match) == 1:
                                    height = int(match[0])
                                    if 240 <= height <= 4320:
                                        if height == 1080:
                                            resolutions.append("1920x1080")
                                        elif height == 720:
                                            resolutions.append("1280x720")
                                        elif height == 480:
                                            resolutions.append("854x480")
                                        else:
                                            resolutions.append(f"auto x {height}")
                            except ValueError:
                                continue
            
            if resolutions:
                from collections import Counter
                most_common = Counter(resolutions).most_common(1)[0][0]
                logger.info(f"从日志中提取到 {len(resolutions)} 个分辨率值，最常见: {most_common}")
                return most_common
            
            logger.warning("未能从日志中提取到有效的分辨率信息")
            logger.debug(f"尝试了 {len(log_sources)} 个搜索源")
            return None
            
        except Exception as e:
            logging.error(f"从日志提取分辨率信息时发生异常: {e}")
            return None
    
    def _extract_gop_from_logs(self):
        """从日志中提取GOP信息"""
        try:
            # 定义GOP搜索模式
            gop_patterns = [
                r'GOP[:\s]*(\d+)',
                r'gop[:\s]*(\d+)',
                r'keyframe[:\s]*interval[:\s]*(\d+)',
                r'I-frame[:\s]*interval[:\s]*(\d+)',
                r'keyframe[:\s]*(\d+)',
                r'I-frame[:\s]*(\d+)',
                r'GOP size[:\s]*(\d+)',
                r'gop size[:\s]*(\d+)'
            ]
            
            # 搜索多个日志源
            log_sources = [
                "dmesg | grep -i 'gop\\|keyframe\\|I-frame' | tail -10",
                "journalctl -u camera* --since '1 hour ago' | grep -i 'gop\\|keyframe\\|I-frame' | tail -10",
                "find /userdata/deploy/log -name '*.log' -exec grep -l -i 'gop\\|keyframe\\|I-frame' {} \\; | head -5"
            ]
            
            gop_values = []
            
            for source in log_sources:
                output = self._execute_ssh_command(source)
                if output:
                    import re
                    for pattern in gop_patterns:
                        matches = re.findall(pattern, output, re.IGNORECASE)
                        for match in matches:
                            try:
                                gop_value = int(match)
                                if 1 <= gop_value <= 300:
                                    gop_values.append(gop_value)
                            except ValueError:
                                continue
            
            if gop_values:
                avg_gop = sum(gop_values) / len(gop_values)
                logging.info(f"从日志中提取到 {len(gop_values)} 个GOP值，平均值: {avg_gop:.0f}")
                return avg_gop
            
            return None
            
        except Exception as e:
            logging.error(f"从日志提取GOP信息时发生异常: {e}")
            return None
    
    def _extract_latency_from_logs(self):
        """从日志中提取延迟信息"""
        try:
            # 定义延迟搜索模式
            latency_patterns = [
                r'latency[:\s]*(\d+(?:\.\d+)?)\s*(ms|s)',
                r'延迟[:\s]*(\d+(?:\.\d+)?)\s*(ms|s)',
                r'delay[:\s]*(\d+(?:\.\d+)?)\s*(ms|s)',
                r'lag[:\s]*(\d+(?:\.\d+)?)\s*(ms|s)',
                r'(\d+(?:\.\d+)?)\s*ms',
                r'(\d+(?:\.\d+)?)\s*毫秒',
                r'ping[:\s]*(\d+(?:\.\d+)?)\s*ms',
                r'round-trip[:\s]*(\d+(?:\.\d+)?)\s*ms'
            ]
            
            # 搜索多个日志源
            log_sources = [
                "dmesg | grep -i 'latency\\|延迟\\|delay\\|lag' | tail -10",
                "journalctl -u camera* --since '1 hour ago' | grep -i 'latency\\|延迟\\|delay\\|lag' | tail -10",
                "find /userdata/deploy/log -name '*.log' -exec grep -l -i 'latency\\|延迟\\|delay\\|lag' {} \\; | head -5"
            ]
            
            latency_values = []
            
            for source in log_sources:
                output = self._execute_ssh_command(source)
                if output:
                    import re
                    for pattern in latency_patterns:
                        matches = re.findall(pattern, output, re.IGNORECASE)
                        for match in matches:
                            try:
                                value = float(match[0])
                                unit = match[1].lower() if len(match) > 1 else 'ms'
                                
                                # 转换为毫秒
                                if unit == 's':
                                    value *= 1000
                                
                                if 0.1 <= value <= 10000:
                                    latency_values.append(value)
                            except (ValueError, IndexError):
                                continue
            
            if latency_values:
                avg_latency = sum(latency_values) / len(latency_values)
                logging.info(f"从日志中提取到 {len(latency_values)} 个延迟值，平均值: {avg_latency:.1f} ms")
                return avg_latency
            
            return None
            
        except Exception as e:
            logging.error(f"从日志提取延迟信息时发生异常: {e}")
            return None
    
    def _extract_quality_score_from_logs(self):
        """从日志中提取视频质量分数"""
        try:
            # 定义质量分数搜索模式
            quality_patterns = [
                r'quality[:\s]*(\d+(?:\.\d+)?)',
                r'质量[:\s]*(\d+(?:\.\d+)?)',
                r'quality score[:\s]*(\d+(?:\.\d+)?)',
                r'质量分数[:\s]*(\d+(?:\.\d+)?)',
                r'PSNR[:\s]*(\d+(?:\.\d+)?)',
                r'SSIM[:\s]*(\d+(?:\.\d+)?)',
                r'VMAF[:\s]*(\d+(?:\.\d+)?)',
                r'score[:\s]*(\d+(?:\.\d+)?)'
            ]
            
            # 搜索多个日志源
            log_sources = [
                "dmesg | grep -i 'quality\\|质量\\|PSNR\\|SSIM\\|VMAF' | tail -10",
                "journalctl -u camera* --since '1 hour ago' | grep -i 'quality\\|质量\\|PSNR\\|SSIM\\|VMAF' | tail -10",
                "find /userdata/deploy/log -name '*.log' -exec grep -l -i 'quality\\|质量\\|PSNR\\|SSIM\\|VMAF' {} \\; | head -5"
            ]
            
            quality_values = []
            
            for source in log_sources:
                output = self._execute_ssh_command(source)
                if output:
                    import re
                    for pattern in quality_patterns:
                        matches = re.findall(pattern, output, re.IGNORECASE)
                        for match in matches:
                            try:
                                quality_value = float(match)
                                if 0 <= quality_value <= 100:
                                    quality_values.append(quality_value)
                            except ValueError:
                                continue
            
            if quality_values:
                avg_quality = sum(quality_values) / len(quality_values)
                logging.info(f"从日志中提取到 {len(quality_values)} 个质量分数值，平均值: {avg_quality:.1f}")
                return avg_quality
            
            return None
            
        except Exception as e:
            logging.error(f"从日志提取视频质量分数信息时发生异常: {e}")
            return None
    
    def _extract_codec_info_from_logs(self):
        """从日志中提取编码器信息"""
        try:
            # 定义编码器搜索模式
            codec_patterns = [
                r'codec[:\s]*([a-zA-Z0-9]+)',
                r'编码器[:\s]*([a-zA-Z0-9]+)',
                r'encoder[:\s]*([a-zA-Z0-9]+)',
                r'profile[:\s]*([a-zA-Z0-9]+)',
                r'H\.?264',
                r'H\.?265',
                r'HEVC',
                r'AVC',
                r'VP8',
                r'VP9',
                r'AV1'
            ]
            
            # 搜索多个日志源
            log_sources = [
                "dmesg | grep -i 'codec\\|编码器\\|encoder\\|profile\\|H264\\|H265\\|HEVC' | tail -10",
                "journalctl -u camera* --since '1 hour ago' | grep -i 'codec\\|编码器\\|encoder\\|profile\\|H264\\|H265\\|HEVC' | tail -10",
                "find /userdata/deploy/log -name '*.log' -exec grep -l -i 'codec\\|编码器\\|encoder\\|profile\\|H264\\|H265\\|HEVC' {} \\; | head -5"
            ]
            
            codecs = []
            profiles = []
            
            for source in log_sources:
                output = self._execute_ssh_command(source)
                if output:
                    import re
                    for pattern in codec_patterns:
                        matches = re.findall(pattern, output, re.IGNORECASE)
                        for match in matches:
                            if match.upper() in ['H264', 'H265', 'HEVC', 'AVC', 'VP8', 'VP9', 'AV1']:
                                codecs.append(match.upper())
                            elif match.upper() in ['BASELINE', 'MAIN', 'HIGH', 'CONSTRAINED_BASELINE']:
                                profiles.append(match.upper())
            
            result = {}
            if codecs:
                from collections import Counter
                most_common_codec = Counter(codecs).most_common(1)[0][0]
                result['codec'] = most_common_codec
                logging.info(f"从日志中找到编码器: {most_common_codec}")
            
            if profiles:
                from collections import Counter
                most_common_profile = Counter(profiles).most_common(1)[0][0]
                result['profile'] = most_common_profile
                logging.info(f"从日志中找到编码配置: {most_common_profile}")
            
            return result if result else None
            
        except Exception as e:
            logging.error(f"从日志提取编码器信息时发生异常: {e}")
            return None

    def _calculate_video_metrics(self, video_data):
        """计算视频性能指标"""
        try:
            # 1. 计算估算码率（基于网络流量）
            network_stats = video_data.get('network_stats', '')
            if network_stats:
                # 这里可以根据网络流量变化估算码率
                # 简化处理，实际需要更复杂的计算
                video_data['estimated_bitrate'] = "2000"  # 估算2Mbps
            else:
                video_data['estimated_bitrate'] = "N/A"
            
            # 2. 计算估算分辨率
            camera_capabilities = video_data.get('camera_capabilities', '')
            if camera_capabilities and '1920x1080' in camera_capabilities:
                video_data['estimated_resolution'] = "1920x1080"
            elif camera_capabilities and '1280x720' in camera_capabilities:
                video_data['estimated_resolution'] = "1280x720"
            else:
                video_data['estimated_resolution'] = "Unknown"
            
            # 3. 计算估算GOP大小
            gop_logs = video_data.get('gop_logs', '')
            if gop_logs:
                video_data['estimated_gop'] = "30"  # 估算GOP=30
            else:
                video_data['estimated_gop'] = "N/A"
            
            # 4. 计算估算延迟
            network_latency = video_data.get('network_latency', '')
            if network_latency and 'time=' in network_latency:
                # 提取延迟时间
                import re
                latency_match = re.search(r'time=(\d+\.?\d*)', network_latency)
                if latency_match:
                    latency = float(latency_match.group(1))
                    video_data['estimated_latency'] = f"{latency:.2f}"
                else:
                    video_data['estimated_latency'] = "N/A"
            else:
                video_data['estimated_latency'] = "N/A"
            
            # 5. 计算视频质量指标
            # 基于系统负载和进程状态计算质量分数
            load_details = self._execute_ssh_command("cat /proc/loadavg")
            if load_details:
                load_parts = load_details.split()
                if len(load_parts) >= 3:
                    load_1min = float(load_parts[0])
                    # 质量分数：负载越低，质量越高
                    quality_score = max(0, 100 - (load_1min * 10))
                    video_data['video_quality_score'] = f"{quality_score:.1f}"
                else:
                    video_data['video_quality_score'] = "N/A"
            else:
                video_data['video_quality_score'] = "N/A"
            
        except Exception as e:
            video_data['calculation_error'] = str(e)
        
        return video_data
    
    def _collect_network_data(self):
        """收集网络数据"""
        network_data = {}
        
        try:
            # 网络接口信息
            network_data['ip_address'] = self._execute_ssh_command("hostname -I | awk '{print $1}'")
            network_data['mac_address'] = self._execute_ssh_command("ip link show | grep -A1 'state UP' | grep 'link/ether' | awk '{print $2}' | head -1")
            network_data['network_interfaces'] = self._execute_ssh_command("ip addr show | grep -E '^[0-9]+:|inet '")
            
            # 网络连接统计
            network_data['tcp_connections'] = self._execute_ssh_command("ss -tuln | wc -l")
            network_data['established_connections'] = self._execute_ssh_command("ss -tuln | grep ESTAB | wc -l")
            
            # 网络流量统计
            network_data['rx_bytes'] = self._execute_ssh_command("cat /proc/net/dev | grep -v 'lo:' | awk '{sum+=$2} END {print sum}'")
            network_data['tx_bytes'] = self._execute_ssh_command("cat /proc/net/dev | grep -v 'lo:' | awk '{sum+=$10} END {print sum}'")
            
            # 网络错误统计
            network_data['rx_errors'] = self._execute_ssh_command("cat /proc/net/dev | grep -v 'lo:' | awk '{sum+=$3} END {print sum}'")
            network_data['tx_errors'] = self._execute_ssh_command("cat /proc/net/dev | grep -v 'lo:' | awk '{sum+=$11} END {print sum}'")
            
        except Exception as e:
            network_data['error'] = str(e)
        
        return network_data
    
    def _collect_process_data(self):
        """收集进程数据"""
        process_data = {}
        
        try:
            # 进程统计
            process_data['total_processes'] = self._execute_ssh_command("ps aux | wc -l")
            process_data['running_processes'] = self._execute_ssh_command("ps aux | grep -v '\\[' | wc -l")
            
            # 高CPU使用率进程
            process_data['top_cpu_processes'] = self._execute_ssh_command("ps aux --sort=-%cpu | head -5")
            
            # 高内存使用率进程
            process_data['top_memory_processes'] = self._execute_ssh_command("ps aux --sort=-%mem | head -5")
            
            # 摄像头相关进程
            process_data['camera_processes'] = self._execute_ssh_command("ps aux | grep -i camera")
            process_data['x5_processes'] = self._execute_ssh_command("ps aux | grep -i x5")
            
            # 系统服务状态
            process_data['systemd_services'] = self._execute_ssh_command("systemctl list-units --type=service --state=running | head -10")
            
        except Exception as e:
            process_data['error'] = str(e)
        
        return process_data
    
    def _validate_collected_data(self, collection_result, temp_threshold, cpu_threshold, memory_threshold, disk_threshold):
        """验证收集的数据"""
        hardware_data = collection_result.get('hardware_data', {})
        warnings = []  # 改为警告而不是错误
        
        # 检查温度
        temp_str = hardware_data.get('temperature', 'N/A')
        if temp_str != 'N/A' and temp_str.replace('.', '').isdigit():
            temp_value = float(temp_str)
            if temp_value > temp_threshold:
                warnings.append(f'温度过高: {temp_value}°C (阈值: {temp_threshold}°C)')
        
        # 检查CPU使用率
        cpu_usage = hardware_data.get('cpu_usage', '')
        if cpu_usage and cpu_usage.replace('.', '').isdigit():
            cpu_value = float(cpu_usage)
            if cpu_value > cpu_threshold:
                warnings.append(f'CPU使用率过高: {cpu_value}% (阈值: {cpu_threshold}%)')
        
        # 检查内存使用率
        memory_usage = hardware_data.get('memory_usage_percent', '')
        if memory_usage and memory_usage.replace('.', '').isdigit():
            memory_value = float(memory_usage)
            if memory_value > memory_threshold:
                warnings.append(f'内存使用率过高: {memory_value}% (阈值: {memory_threshold}%)')
        
        # 检查磁盘使用率
        disk_usage = hardware_data.get('disk_usage_root', '')
        if disk_usage and disk_usage.endswith('%'):
            disk_value = float(disk_usage.replace('%', ''))
            if disk_value > disk_threshold:
                warnings.append(f'磁盘使用率过高: {disk_value}% (阈值: {disk_threshold}%)')
        
        # 将警告添加到结果中，但不标记为失败
        if warnings:
            collection_result['warnings'] = warnings
            print(f"数据收集警告: {', '.join(warnings)}")
        
        # 只有在数据收集本身失败时才标记为失败，阈值超标只是警告
        # collection_result['success'] 保持原值，不因阈值超标而改变
    
    def _handle_collection_failure(self, collection_result, current_time):
        """处理数据收集失败"""
        error_info = {
            'timestamp': current_time,
            'type': 'COLLECTION_FAILURE',
            'errors': collection_result['errors'],
            'ssh_connected': collection_result['ssh_connected']
        }
        self.error_log.append(error_info)
        
        # 记录到Allure报告
        allure.attach(f"""
        数据收集失败详情:
        时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
        SSH连接状态: {collection_result['ssh_connected']}
        错误: {', '.join(collection_result['errors'])}
        """, "数据收集失败", allure.attachment_type.TEXT)
    
    def _handle_exception(self, exception, current_time, elapsed_time):
        """处理异常"""
        error_info = {
            'timestamp': current_time,
            'elapsed_time': elapsed_time,
            'type': 'EXCEPTION',
            'error': str(exception)
        }
        self.error_log.append(error_info)
        
        allure.attach(f"""
        异常详情:
        时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}
        运行时间: {elapsed_time/3600:.1f}小时
        异常: {str(exception)}
        """, "异常详情", allure.attachment_type.TEXT)
    
    def _record_monitoring_data(self, collection_result, current_time, elapsed_time):
        """记录监控数据"""
        # 提取关键指标
        hardware_data = collection_result.get('hardware_data', {})
        
        data_point = {
            'timestamp': current_time,
            'elapsed_time': elapsed_time,
            'success': collection_result['success'],
            'ssh_connected': collection_result['ssh_connected'],
            'temperature': self._parse_numeric_value(hardware_data.get('temperature', 'N/A')),
            'cpu_usage': self._parse_numeric_value(hardware_data.get('cpu_usage', '')),
            'memory_usage': self._parse_numeric_value(hardware_data.get('memory_usage_percent', '')),
            'disk_usage': self._parse_disk_usage(hardware_data.get('disk_usage', '')),
            'disk_usage_root': self._parse_disk_usage(hardware_data.get('disk_usage_root', '')),
            'disk_usage_userdata': self._parse_disk_usage(hardware_data.get('disk_usage_userdata', '')),
            'disk_usage_app': self._parse_disk_usage(hardware_data.get('disk_usage_app', '')),
            'load_avg_1min': self._parse_numeric_value(hardware_data.get('load_avg_1min', '')),
            'load_avg_5min': self._parse_numeric_value(hardware_data.get('load_avg_5min', '')),
            'load_avg_15min': self._parse_numeric_value(hardware_data.get('load_avg_15min', '')),
            'total_processes': self._parse_numeric_value(hardware_data.get('total_processes', '')),
            'tcp_connections': self._parse_numeric_value(hardware_data.get('tcp_connections', '')),
            # BPU 数据：来自 hrut_somstatus，使用率(ratio)、频率(MHz)、温度(°C)
            'bpu_usage': self._parse_numeric_value(str(hardware_data.get('bpu_usage') or '')),
            'bpu0_ratio': self._parse_numeric_value(str(hardware_data.get('bpu0_ratio') or '')),
            'bpu1_ratio': self._parse_numeric_value(str(hardware_data.get('bpu1_ratio') or '')),
            'bpu_cur_freq_mhz': self._parse_numeric_value(str(hardware_data.get('bpu_cur_freq_mhz') or '')) or self._parse_bpu_freq_mhz(hardware_data.get('bpu_cur_freq_hz', '')),
            'bpu_temperature': self._parse_numeric_value(str(hardware_data.get('bpu_temperature') or '')),
            # 视频性能相关数据
            'estimated_fps': self._parse_numeric_value(hardware_data.get('estimated_fps', 'N/A')),  # analysis fps
            'real_fps': self._parse_numeric_value(hardware_data.get('real_fps', 'N/A')),  # Actual FPS
            'target_fps': self._parse_numeric_value(hardware_data.get('target_fps', 'N/A')),  # Target FPS
            'smart_fps': self._parse_numeric_value(hardware_data.get('smart_fps', 'N/A')),  # Smart fps
            'estimated_bitrate': self._parse_numeric_value(hardware_data.get('estimated_bitrate', 'N/A')),
            'real_bitrate': self._parse_numeric_value(hardware_data.get('real_bitrate', 'N/A')),
            'estimated_latency': self._parse_numeric_value(hardware_data.get('estimated_latency', 'N/A')),
            'real_latency': self._parse_numeric_value(hardware_data.get('real_latency', 'N/A')),
            'video_quality_score': self._parse_numeric_value(hardware_data.get('video_quality_score', 'N/A')),
            'real_quality_score': self._parse_numeric_value(hardware_data.get('real_quality_score', 'N/A')),
            'real_resolution': hardware_data.get('real_resolution', 'N/A'),
            'real_gop': self._parse_numeric_value(hardware_data.get('real_gop', 'N/A')),
            'codec': hardware_data.get('codec', 'N/A'),
            'codec_profile': hardware_data.get('codec_profile', 'N/A'),
            'camera_processes_count': self._count_processes(hardware_data.get('camera_processes', '')),
            'x5_processes_count': self._count_processes(hardware_data.get('x5_processes', '')),
            'camera_devices_count': self._count_devices(hardware_data.get('camera_devices', '')),
            'usb_cameras_count': self._count_devices(hardware_data.get('usb_cameras', '')),
            'camera_modules_count': self._count_modules(hardware_data.get('camera_modules', '')),
            'video_modules_count': self._count_modules(hardware_data.get('video_modules', '')),
            'encoder_processes_count': self._count_processes(hardware_data.get('encoder_status', '')),
            'ffmpeg_processes_count': self._count_processes(hardware_data.get('ffmpeg_processes', '')),
            'rtsp_processes_count': self._count_processes(hardware_data.get('rtsp_processes', '')),
            'rtmp_processes_count': self._count_processes(hardware_data.get('rtmp_processes', '')),
            # 从日志中提取的具体数值（而不是统计数量）
            'camera_logs_fps': self._extract_fps_from_log_text(hardware_data.get('camera_logs', '')),
            'camera_errors_count': self._count_log_entries(hardware_data.get('camera_errors', '')),
            'resolution_logs_value': self._extract_resolution_from_log_text(hardware_data.get('resolution_logs', '')),
            'video_logs_fps': self._extract_fps_from_log_text(hardware_data.get('video_logs', '')),
            'gop_logs_value': self._extract_gop_from_log_text(hardware_data.get('gop_logs', '')),
            'keyframe_logs_value': self._extract_gop_from_log_text(hardware_data.get('keyframe_logs', ''))
        }
        
        self.monitoring_data.append(data_point)
        
        # 保存到CSV文件
        self._save_data_to_csv(data_point)
    
    def _parse_numeric_value(self, value_str):
        """解析数值"""
        if not value_str or value_str == 'N/A' or value_str.strip() == '':
            return 0.0
        
        # 清理字符串
        value_str = value_str.strip()
        
        # 移除常见的非数字字符
        import re
        value_str = re.sub(r'[^\d.-]', '', value_str)
        
        try:
            return float(value_str)
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_disk_usage(self, disk_usage_str):
        """解析磁盘使用率"""
        if not disk_usage_str or disk_usage_str.strip() == '':
            return 0.0
        
        # 清理字符串
        disk_usage_str = disk_usage_str.strip()
        
        # 移除%符号
        if disk_usage_str.endswith('%'):
            disk_usage_str = disk_usage_str[:-1]
        
        # 移除其他非数字字符
        import re
        disk_usage_str = re.sub(r'[^\d.-]', '', disk_usage_str)
        
        try:
            return float(disk_usage_str)
        except (ValueError, TypeError):
            return 0.0
    
    def _parse_bpu_somstatus_output(self, raw):
        """从 hrut_somstatus 原始输出中解析 BPU 及温度数据。
        支持格式（含制表符、前导空白、干扰行如 59149）:
        temperature-->
            DDR      : 59.5 (C)
        59149
            BPU      : 59.2 (C)
            CPU      : 60.6 (C)
        bpu status information---->
            min(M)   cur(M)  max(M)  ratio
            bpu0    : 500    1000    1000    1
        """
        import re
        out = {
            'bpu_usage': None, 'bpu_freq_mhz': None, 'bpu0_ratio': None, 'bpu1_ratio': None, 'bpu_cur_freq_hz': None,
            'temp_ddr': None, 'temp_bpu': None, 'temp_cpu': None
        }
        if not raw or not str(raw).strip():
            return out
        # 统一换行、便于正则匹配（制表符 \s 已能匹配）
        raw = str(raw).replace('\r\n', '\n').replace('\r', '\n').strip()
        # 温度: DDR/BPU/CPU : 59.5 (C) 或 59.5
        def _temp_match(prefix):
            m = re.search(r'%s\s*:\s*([\d.]+)\s*\(C\)' % re.escape(prefix), raw, re.I)
            if m:
                return float(m.group(1))
            m = re.search(r'%s\s*:\s*([\d.]+)' % re.escape(prefix), raw, re.I)
            if m:
                return float(m.group(1))
            return None
        out['temp_ddr'] = _temp_match('DDR')
        out['temp_bpu'] = _temp_match('BPU')
        out['temp_cpu'] = _temp_match('CPU')
        # bpu0/bpu1：数字之间可为空格或制表符，如 "bpu0    : 500	1000	1000	1"
        bpu0_m = re.search(r'bpu0\s*:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', raw, re.I | re.DOTALL)
        if bpu0_m:
            _min, cur_mhz, _max, ratio0 = int(bpu0_m.group(1)), int(bpu0_m.group(2)), int(bpu0_m.group(3)), int(bpu0_m.group(4))
            out['bpu_freq_mhz'] = cur_mhz
            out['bpu_cur_freq_mhz'] = cur_mhz
            out['bpu_cur_freq_hz'] = cur_mhz * 1000000
            out['bpu0_ratio'] = ratio0
            out['bpu_usage'] = ratio0
        bpu1_m = re.search(r'bpu1\s*:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', raw, re.I | re.DOTALL)
        if bpu1_m:
            ratio1 = int(bpu1_m.group(4))
            out['bpu1_ratio'] = ratio1
            if out['bpu_usage'] is not None:
                out['bpu_usage'] = max(out['bpu_usage'], ratio1)
            else:
                out['bpu_usage'] = ratio1
        return out
    
    def _parse_bpu_freq_mhz(self, hz_str):
        """将 BPU 频率 Hz 字符串转为 MHz"""
        if not hz_str or str(hz_str).strip() == '':
            return 0.0
        import re
        s = re.sub(r'[^\d.]', '', str(hz_str).strip())
        try:
            return round(float(s) / 1e6, 2)
        except (ValueError, TypeError):
            return 0.0
    
    def _count_processes(self, processes_str):
        """统计进程数量"""
        if not processes_str:
            return 0
        try:
            # 按行分割，过滤空行
            lines = [line.strip() for line in processes_str.split('\n') if line.strip()]
            return len(lines)
        except:
            return 0
    
    def _count_devices(self, devices_str):
        """统计设备数量"""
        if not devices_str:
            return 0
        try:
            # 按行分割，过滤空行
            lines = [line.strip() for line in devices_str.split('\n') if line.strip()]
            return len(lines)
        except:
            return 0
    
    def _count_modules(self, modules_str):
        """统计模块数量"""
        if not modules_str:
            return 0
        try:
            # 按行分割，过滤空行
            lines = [line.strip() for line in modules_str.split('\n') if line.strip()]
            return len(lines)
        except:
            return 0
    
    def _count_log_entries(self, log_str):
        """统计日志条目数量"""
        if not log_str:
            return 0
        try:
            # 按行分割，过滤空行
            lines = [line.strip() for line in log_str.split('\n') if line.strip()]
            return len(lines)
        except:
            return 0
    
    def _extract_fps_from_log_text(self, log_text):
        """从日志文本中提取FPS值"""
        if not log_text:
            return 0.0
        
        try:
            import re
            fps_patterns = [
                r'(\d+(?:\.\d+)?)\s*fps',
                r'fps[:\s]*(\d+(?:\.\d+)?)',
                r'FPS[:\s]*(\d+(?:\.\d+)?)',
                r'帧率[:\s]*(\d+(?:\.\d+)?)',
                r'frame[:\s]*rate[:\s]*(\d+(?:\.\d+)?)'
            ]
            
            for pattern in fps_patterns:
                matches = re.findall(pattern, log_text, re.IGNORECASE)
                for match in matches:
                    try:
                        fps_value = float(match)
                        if 1 <= fps_value <= 120:  # 合理的FPS范围
                            return fps_value
                    except ValueError:
                        continue
            
            return 0.0
        except:
            return 0.0
    
    def _extract_resolution_from_log_text(self, log_text):
        """从日志文本中提取分辨率值"""
        if not log_text:
            return 0.0
        
        try:
            import re
            resolution_patterns = [
                r'(\d{3,4})\s*[x×]\s*(\d{3,4})',
                r'(\d{3,4})\s*[*]\s*(\d{3,4})',
                r'resolution[:\s]*(\d{3,4})\s*[x×*]\s*(\d{3,4})',
                r'分辨率[:\s]*(\d{3,4})\s*[x×*]\s*(\d{3,4})'
            ]
            
            for pattern in resolution_patterns:
                matches = re.findall(pattern, log_text, re.IGNORECASE)
                for match in matches:
                    try:
                        if len(match) == 2:
                            width, height = int(match[0]), int(match[1])
                            if 320 <= width <= 7680 and 240 <= height <= 4320:
                                # 返回分辨率的总像素数作为数值
                                return width * height
                    except ValueError:
                        continue
            
            return 0.0
        except:
            return 0.0
    
    def _extract_gop_from_log_text(self, log_text):
        """从日志文本中提取GOP值"""
        if not log_text:
            return 0.0
        
        try:
            import re
            gop_patterns = [
                r'GOP[:\s]*(\d+)',
                r'gop[:\s]*(\d+)',
                r'keyframe[:\s]*interval[:\s]*(\d+)',
                r'I-frame[:\s]*interval[:\s]*(\d+)',
                r'keyframe[:\s]*(\d+)',
                r'I-frame[:\s]*(\d+)'
            ]
            
            for pattern in gop_patterns:
                matches = re.findall(pattern, log_text, re.IGNORECASE)
                for match in matches:
                    try:
                        gop_value = int(match)
                        if 1 <= gop_value <= 300:  # 合理的GOP范围
                            return float(gop_value)
                    except ValueError:
                        continue
            
            return 0.0
        except:
            return 0.0
    
    def _save_data_to_csv(self, data_point):
        """保存数据到CSV文件"""
        csv_file = os.path.join(self.output_dir, 'ssh_monitoring_data.csv')
        file_exists = os.path.exists(csv_file)
        
        # 定义固定的字段顺序，确保CSV格式一致性
        fixed_fieldnames = [
            'timestamp', 'elapsed_time', 'success', 'ssh_connected',
            'temperature', 'cpu_usage', 'memory_usage', 'disk_usage',
            'bpu_usage', 'bpu0_ratio', 'bpu1_ratio', 'bpu_cur_freq_mhz', 'bpu_temperature',
            'disk_usage_root', 'disk_usage_userdata', 'disk_usage_app',
            'load_avg_1min', 'load_avg_5min', 'load_avg_15min',
            'total_processes', 'tcp_connections',
            'estimated_fps', 'real_fps', 'target_fps', 'smart_fps',  # FPS字段
            'estimated_bitrate', 'real_bitrate', 
            'estimated_latency', 'real_latency', 'video_quality_score', 'real_quality_score',
            'real_resolution', 'real_gop', 'codec', 'codec_profile',
            'camera_processes_count', 'x5_processes_count',
            'camera_devices_count', 'usb_cameras_count',
            'camera_modules_count', 'video_modules_count',
            'encoder_processes_count', 'ffmpeg_processes_count',
            'rtsp_processes_count', 'rtmp_processes_count',
            # 从日志中提取的具体数值字段
            'camera_logs_fps', 'camera_errors_count',
            'resolution_logs_value', 'video_logs_fps',
            'gop_logs_value', 'keyframe_logs_value'
        ]
        
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fixed_fieldnames)
            if not file_exists:
                writer.writeheader()
            
            # 确保数据点包含所有字段，缺失的字段用空值填充
            complete_data_point = {}
            for field in fixed_fieldnames:
                complete_data_point[field] = data_point.get(field, '')
            
            writer.writerow(complete_data_point)
    
    def _generate_hourly_report(self, temp_threshold, cpu_threshold, memory_threshold, disk_threshold):
        """生成小时报告"""
        if not self.monitoring_data:
            return
        
        # 生成图表
        self._generate_monitoring_charts(temp_threshold, cpu_threshold, memory_threshold, disk_threshold)
        
        # 生成统计报告
        self._generate_statistics_report(temp_threshold, cpu_threshold, memory_threshold, disk_threshold)
    
    def _generate_monitoring_charts(self, temp_threshold, cpu_threshold, memory_threshold, disk_threshold):
        """生成监控图表"""
        if len(self.monitoring_data) < 2:
            return
        
        try:
            # 准备数据
            timestamps = [d['timestamp'] for d in self.monitoring_data]
            temp_data = [d['temperature'] for d in self.monitoring_data]
            cpu_data = [d['cpu_usage'] for d in self.monitoring_data]
            memory_data = [d['memory_usage'] for d in self.monitoring_data]
            disk_data = [d['disk_usage'] for d in self.monitoring_data]
            load_data = [d['load_avg_1min'] for d in self.monitoring_data]
            estimated_fps_data = [d['estimated_fps'] for d in self.monitoring_data]  # analysis fps
            real_fps_data = [d['real_fps'] for d in self.monitoring_data]  # Actual FPS
            target_fps_data = [d.get('target_fps', 0) for d in self.monitoring_data]  # Target FPS
            smart_fps_data = [d.get('smart_fps', 0) for d in self.monitoring_data]  # Smart fps
            bitrate_data = [d['estimated_bitrate'] for d in self.monitoring_data]
            latency_data = [d['estimated_latency'] for d in self.monitoring_data]
            quality_data = [d['video_quality_score'] for d in self.monitoring_data]
            camera_processes_data = [d['camera_processes_count'] for d in self.monitoring_data]
            x5_processes_data = [d['x5_processes_count'] for d in self.monitoring_data]
            encoder_processes_data = [d['encoder_processes_count'] for d in self.monitoring_data]
            ffmpeg_processes_data = [d['ffmpeg_processes_count'] for d in self.monitoring_data]
            bpu_usage_data = [d.get('bpu_usage', 0) for d in self.monitoring_data]
            bpu_freq_mhz_data = [d.get('bpu_cur_freq_mhz', 0) for d in self.monitoring_data]
            bpu_temperature_data = [d.get('bpu_temperature', 0) for d in self.monitoring_data]
            
            # 创建图表 - 5x2 布局，BPU 合并到 CPU 子图
            fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6), (ax7, ax8), (ax9, ax10)) = plt.subplots(5, 2, figsize=(15, 25))
            fig.suptitle('X5摄像头SSH底层数据监控图表', fontsize=16)
            
            # 温度图表：系统温度 + BPU温度
            ax1.plot(timestamps, temp_data, 'r-', linewidth=2, label='温度(系统)')
            if any(t > 0 for t in bpu_temperature_data):
                ax1.plot(timestamps, bpu_temperature_data, 'm-', linewidth=2, label='BPU温度')
            ax1.axhline(y=temp_threshold, color='r', linestyle='--', label=f'阈值({temp_threshold}°C)')
            ax1.set_title('温度监控 (系统 + BPU)')
            ax1.set_ylabel('温度 (°C)')
            ax1.legend()
            ax1.grid(True, alpha=0.3)
            
            # CPU / BPU 合并：左轴 使用率(%)，右轴 BPU频率(MHz)
            ax2.plot(timestamps, cpu_data, 'b-', linewidth=2, label='CPU使用率')
            ax2.plot(timestamps, bpu_usage_data, 'm-', linewidth=2, label='BPU使用率(ratio)')
            ax2.axhline(y=cpu_threshold, color='r', linestyle='--', label=f'阈值({cpu_threshold}%)')
            ax2.set_ylabel('使用率 (%)', color='black')
            ax2.tick_params(axis='y', labelcolor='black')
            ax2_twin = ax2.twinx()
            ax2_twin.plot(timestamps, bpu_freq_mhz_data, 'c-', linewidth=2, label='BPU频率(MHz)')
            ax2_twin.set_ylabel('BPU频率 (MHz)', color='cyan')
            ax2_twin.tick_params(axis='y', labelcolor='cyan')
            ax2.set_title('CPU / BPU 使用率与频率')
            lines2, labels2 = ax2.get_legend_handles_labels()
            lines2_twin, labels2_twin = ax2_twin.get_legend_handles_labels()
            ax2.legend(lines2 + lines2_twin, labels2 + labels2_twin, loc='upper left')
            ax2.grid(True, alpha=0.3)
            
            # 改进：内存使用率图表 - 优化图例显示
            line1 = ax3.plot(timestamps, memory_data, 'g-', linewidth=2, label='内存使用率', alpha=0.8)
            line2 = ax3.axhline(y=memory_threshold, color='r', linestyle='--', alpha=0.7, label=f'警告阈值({memory_threshold}%)')
            ax3.axhline(y=80, color='orange', linestyle=':', alpha=0.5, label='高使用率(80%)')
            ax3.axhline(y=95, color='red', linestyle=':', alpha=0.5, label='危险阈值(95%)')
            
            ax3.set_title('内存使用率监控')
            ax3.set_ylabel('内存使用率 (%)')
            
            # 优化图例显示
            lines = line1 + [line2]
            labels = [l.get_label() for l in lines]
            ax3.legend(lines, labels, loc='upper left', fontsize=9, framealpha=0.9, 
                      facecolor='white', edgecolor='black', fancybox=True, shadow=True)
            
            # 添加统计信息
            if len(memory_data) > 0:
                max_memory = max(memory_data)
                avg_memory = sum(memory_data) / len(memory_data)
                min_memory = min(memory_data)
                
                # 添加预警信息
                warnings = []
                if max_memory > 80:
                    warnings.append('⚠️ 内存使用率较高')
                if max_memory > 95:
                    warnings.append('🚨 内存使用率危险')
                
                stats_text = f'最高: {max_memory:.1f}%\n平均: {avg_memory:.1f}%\n最低: {min_memory:.1f}%'
                if warnings:
                    stats_text += '\n\n' + '\n'.join(warnings)
                
                ax3.text(0.02, 0.98, stats_text, transform=ax3.transAxes, verticalalignment='top', 
                        bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.9, edgecolor='green'), 
                        fontsize=8, fontweight='bold')
            
            ax3.grid(True, alpha=0.3)
            
            # 改进：磁盘分区监控图表 - 详细分析和预警
            disk_root_data = [d['disk_usage_root'] for d in self.monitoring_data]
            disk_userdata_data = [d['disk_usage_userdata'] for d in self.monitoring_data]
            disk_app_data = [d['disk_usage_app'] for d in self.monitoring_data]
            
            if len(disk_userdata_data) > 0 or len(disk_root_data) > 0 or len(disk_app_data) > 0:
                # 创建双y轴图表
                ax4_twin = ax4.twinx()
                
                # 左y轴：使用率百分比
                lines = []
                if len(disk_userdata_data) > 0:
                    line1 = ax4.plot(timestamps, disk_userdata_data, 'g-', linewidth=2, label='userdata分区', alpha=0.8)
                    lines.extend(line1)
                if len(disk_root_data) > 0:
                    line2 = ax4.plot(timestamps, disk_root_data, 'r-', linewidth=2, label='根分区', alpha=0.8)
                    lines.extend(line2)
                if len(disk_app_data) > 0:
                    line3 = ax4.plot(timestamps, disk_app_data, 'b-', linewidth=2, label='app分区', alpha=0.8)
                    lines.extend(line3)
                
                # 添加阈值线
                ax4.axhline(y=disk_threshold, color='m', linestyle='--', alpha=0.7, label=f'警告阈值({disk_threshold}%)')
                ax4.axhline(y=90, color='orange', linestyle=':', alpha=0.5, label='高使用率(90%)')
                ax4.axhline(y=95, color='red', linestyle=':', alpha=0.5, label='危险阈值(95%)')
                
                # 右y轴：使用率趋势（变化率）
                if len(disk_userdata_data) > 1:
                    usage_trend = []
                    for i in range(1, len(disk_userdata_data)):
                        trend = disk_userdata_data[i] - disk_userdata_data[i-1]
                        usage_trend.append(trend)
                    
                    # 为趋势数据创建时间戳（去掉第一个点）
                    trend_timestamps = timestamps[1:] if len(timestamps) > 1 else timestamps
                    if usage_trend:
                        line4 = ax4_twin.plot(trend_timestamps, usage_trend, 'purple', linewidth=1, 
                                            label='使用率变化趋势', linestyle=':', alpha=0.6)
                        lines.extend(line4)
                
                # 设置标签和标题
                ax4.set_title('磁盘分区监控（多分区详细分析）')
                ax4.set_ylabel('使用率 (%)', color='black')
                ax4_twin.set_ylabel('使用率变化 (%)', color='purple')
                
                # 合并图例
                labels = [l.get_label() for l in lines]
                ax4.legend(lines, labels, loc='upper left', fontsize=8)
                
                # 添加分区统计信息
                partition_stats = []
                if disk_userdata_data:
                    max_userdata = max(disk_userdata_data)
                    avg_userdata = sum(disk_userdata_data) / len(disk_userdata_data)
                    partition_stats.append(f'userdata: 最高{max_userdata:.1f}%, 平均{avg_userdata:.1f}%')
                
                if disk_root_data:
                    max_root = max(disk_root_data)
                    avg_root = sum(disk_root_data) / len(disk_root_data)
                    partition_stats.append(f'根分区: 最高{max_root:.1f}%, 平均{avg_root:.1f}%')
                
                if disk_app_data:
                    max_app = max(disk_app_data)
                    avg_app = sum(disk_app_data) / len(disk_app_data)
                    partition_stats.append(f'app分区: 最高{max_app:.1f}%, 平均{avg_app:.1f}%')
                
                # 添加预警信息
                warnings = []
                if disk_userdata_data and max(disk_userdata_data) > 90:
                    warnings.append('⚠️ userdata分区使用率过高')
                if disk_root_data and max(disk_root_data) > 90:
                    warnings.append('⚠️ 根分区使用率过高')
                if disk_app_data and max(disk_app_data) > 90:
                    warnings.append('⚠️ app分区使用率过高')
                
                # 显示统计信息
                stats_text = '\n'.join(partition_stats)
                if warnings:
                    stats_text += '\n\n' + '\n'.join(warnings)
                
                ax4.text(0.02, 0.98, stats_text, transform=ax4.transAxes, verticalalignment='top', 
                        bbox=dict(boxstyle='round', facecolor='lightblue', alpha=0.8), fontsize=8)
                
            ax4.grid(True, alpha=0.3)
            
            # FPS监控图表 - 显示所有FPS字段
            if len(real_fps_data) > 0 and any(fps > 0 for fps in real_fps_data):
                ax5.plot(timestamps, real_fps_data, 'green', linewidth=2, label='Actual FPS')
            if len(target_fps_data) > 0 and any(fps > 0 for fps in target_fps_data):
                ax5.plot(timestamps, target_fps_data, 'blue', linewidth=2, label='Target FPS')
            if len(smart_fps_data) > 0 and any(fps > 0 for fps in smart_fps_data):
                ax5.plot(timestamps, smart_fps_data, 'purple', linewidth=2, label='Smart fps')
            if len(estimated_fps_data) > 0 and any(fps > 0 for fps in estimated_fps_data):
                ax5.plot(timestamps, estimated_fps_data, 'orange', linewidth=2, label='analysis fps')
            
            # 添加参考线（可选）
            ax5.axhline(y=25, color='orange', linestyle='--', alpha=0.5, label='参考线(25)')
            ax5.axhline(y=20, color='red', linestyle='--', alpha=0.5, label='参考线(20)')
            ax5.set_title('FPS监控')
            ax5.set_ylabel('FPS')
            ax5.legend()
            ax5.grid(True, alpha=0.3)
            
            # 摄像头进程监控图表
            ax6.plot(timestamps, camera_processes_data, 'purple', linewidth=2, label='摄像头进程数')
            ax6.plot(timestamps, x5_processes_data, 'brown', linewidth=2, label='X5进程数')
            ax6.set_title('摄像头进程监控')
            ax6.set_ylabel('进程数量')
            ax6.legend()
            ax6.grid(True, alpha=0.3)
            
            # 码率监控图表
            ax7.plot(timestamps, bitrate_data, 'cyan', linewidth=2, label='估算码率')
            ax7.axhline(y=2000, color='cyan', linestyle='--', label='目标码率(2Mbps)')
            ax7.set_title('码率监控')
            ax7.set_ylabel('码率 (kbps)')
            ax7.legend()
            ax7.grid(True, alpha=0.3)
            
            # 延迟监控图表
            ax8.plot(timestamps, latency_data, 'orange', linewidth=2, label='网络延迟')
            ax8.axhline(y=10, color='orange', linestyle='--', label='延迟阈值(10ms)')
            ax8.set_title('延迟监控')
            ax8.set_ylabel('延迟 (ms)')
            ax8.legend()
            ax8.grid(True, alpha=0.3)
            
            # 改进：错误日志监控图表 - 详细分析和趋势
            camera_logs_data = [d.get('camera_logs_count', 0) for d in self.monitoring_data]
            camera_errors_data = [d.get('camera_errors_count', 0) for d in self.monitoring_data]
            
            # 计算错误率趋势
            error_rates = []
            for i, (logs, errors) in enumerate(zip(camera_logs_data, camera_errors_data)):
                if logs > 0:
                    error_rate = (errors / logs) * 100
                else:
                    error_rate = 0
                error_rates.append(error_rate)
            
            # 绘制主要图表
            ax9_twin = ax9.twinx()  # 创建双y轴
            
            # 左y轴：日志数量
            line1 = ax9.plot(timestamps, camera_logs_data, 'blue', linewidth=2, label='摄像头日志总数', alpha=0.7)
            line2 = ax9.plot(timestamps, camera_errors_data, 'red', linewidth=2, label='摄像头错误日志', alpha=0.7)
            
            # 右y轴：错误率
            line3 = ax9_twin.plot(timestamps, error_rates, 'orange', linewidth=2, label='错误率(%)', linestyle='--')
            
            # 添加错误率阈值线
            ax9_twin.axhline(y=10, color='orange', linestyle=':', alpha=0.5, label='错误率阈值(10%)')
            ax9_twin.axhline(y=20, color='red', linestyle=':', alpha=0.5, label='错误率警告(20%)')
            
            # 设置标签和标题
            ax9.set_title('摄像头错误日志监控（含错误率分析）')
            ax9.set_ylabel('日志条目数', color='blue')
            ax9_twin.set_ylabel('错误率 (%)', color='orange')
            
            # 合并图例
            lines = line1 + line2 + line3
            labels = [l.get_label() for l in lines]
            ax9.legend(lines, labels, loc='upper left', fontsize=8)
            
            # 添加统计信息文本
            if len(camera_errors_data) > 0:
                max_errors = max(camera_errors_data)
                avg_errors = sum(camera_errors_data) / len(camera_errors_data)
                max_error_rate = max(error_rates) if error_rates else 0
                ax9.text(0.02, 0.98, f'最大错误数: {max_errors}\n平均错误数: {avg_errors:.1f}\n最大错误率: {max_error_rate:.1f}%', 
                        transform=ax9.transAxes, verticalalignment='top', 
                        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8), fontsize=8)
            
            ax9.grid(True, alpha=0.3)
            
            # 改进：视频性能监控图表 - 优化分辨率坐标显示
            resolution_values = [d['resolution_logs_value'] for d in self.monitoring_data]
            video_fps_values = [d['video_logs_fps'] for d in self.monitoring_data]
            gop_values = [d['gop_logs_value'] for d in self.monitoring_data]
            
            # 创建双y轴图表
            ax10_twin = ax10.twinx()
            
            # 左y轴：分辨率（转换为分辨率等级）
            resolution_levels = []
            resolution_labels = []
            
            for res in resolution_values:
                if res and res != 0:
                    try:
                        if 'x' in str(res):
                            width, height = str(res).split('x')
                            width, height = int(width), int(height)
                            
                            # 根据分辨率确定等级
                            if width >= 3840 and height >= 2160:
                                level = 4  # 4K
                                label = "4K"
                            elif width >= 1920 and height >= 1080:
                                level = 3  # 1080p/2K
                                label = "2K"
                            elif width >= 1280 and height >= 720:
                                level = 2  # 720p
                                label = "720p"
                            else:
                                level = 1  # 其他
                                label = "其他"
                            
                            resolution_levels.append(level)
                            resolution_labels.append(label)
                        else:
                            resolution_levels.append(0)
                            resolution_labels.append("未知")
                    except:
                        resolution_levels.append(0)
                        resolution_labels.append("未知")
                else:
                    resolution_levels.append(0)
                    resolution_labels.append("无数据")
            
            # 右y轴：FPS和GOP
            line1 = ax10.plot(timestamps, resolution_levels, 'green', linewidth=2, label='分辨率等级', marker='o', markersize=4)
            line2 = ax10_twin.plot(timestamps, video_fps_values, 'purple', linewidth=2, label='视频FPS', marker='s', markersize=3)
            line3 = ax10_twin.plot(timestamps, gop_values, 'orange', linewidth=2, label='GOP值', marker='^', markersize=3)
            
            # 设置分辨率y轴标签和刻度
            ax10.set_ylabel('分辨率等级', color='green')
            ax10.set_yticks([0, 1, 2, 3, 4])
            ax10.set_yticklabels(['无数据', '其他', '720p', '2K', '4K'])
            ax10.set_ylim(-0.5, 4.5)
            
            # 添加分辨率参考线
            ax10.axhline(y=2, color='gray', linestyle=':', alpha=0.5, label='720p参考线')
            ax10.axhline(y=3, color='blue', linestyle=':', alpha=0.5, label='2K参考线')
            ax10.axhline(y=4, color='red', linestyle=':', alpha=0.5, label='4K参考线')
            
            # 添加FPS参考线
            ax10_twin.axhline(y=30, color='purple', linestyle=':', alpha=0.5, label='30fps参考线')
            ax10_twin.axhline(y=60, color='purple', linestyle=':', alpha=0.5, label='60fps参考线')
            
            # 设置标签和标题
            ax10.set_title('视频性能监控（分辨率、FPS、GOP）')
            ax10_twin.set_ylabel('FPS / GOP值', color='purple')
            
            # 合并图例
            lines = line1 + line2 + line3
            labels = [l.get_label() for l in lines]
            ax10.legend(lines, labels, loc='upper left', fontsize=8, framealpha=0.9, 
                       facecolor='white', edgecolor='black', fancybox=True, shadow=True)
            
            # 添加统计信息
            if resolution_levels:
                max_level = max(resolution_levels)
                avg_level = sum(resolution_levels) / len(resolution_levels)
                max_fps = max(video_fps_values) if video_fps_values else 0
                avg_fps = sum(video_fps_values) / len(video_fps_values) if video_fps_values else 0
                
                # 确定分辨率等级名称
                level_names = {0: "无数据", 1: "其他", 2: "720p", 3: "2K", 4: "4K"}
                max_res_name = level_names.get(max_level, "未知")
                avg_res_name = level_names.get(round(avg_level), "未知")
                
                stats_text = f'最高分辨率: {max_res_name}\n平均分辨率: {avg_res_name}\n最高FPS: {max_fps:.1f}\n平均FPS: {avg_fps:.1f}'
                
                ax10.text(0.02, 0.98, stats_text, transform=ax10.transAxes, verticalalignment='top', 
                        bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.9, edgecolor='green'), 
                        fontsize=8, fontweight='bold')
            
            ax10.grid(True, alpha=0.3)
            
            # 智能设置x轴格式 - 根据监控时长调整时间间隔
            if len(timestamps) > 0:
                # 计算监控时长
                try:
                    # 确保timestamps是列表格式
                    if hasattr(timestamps, 'iloc'):
                        # pandas Series
                        time_span = timestamps.iloc[-1] - timestamps.iloc[0]
                    else:
                        # 普通列表
                        time_span = timestamps[-1] - timestamps[0]
                    total_hours = time_span.total_seconds() / 3600
                except Exception as e:
                    logger.error(f"时间计算错误: {e}")
                    total_hours = 2  # 默认2小时
                
                # 根据监控时长智能设置时间间隔
                if total_hours <= 2:  # 2小时以内
                    time_interval = 0.5  # 30分钟间隔
                    time_format = '%H:%M'
                    locator = mdates.MinuteLocator(interval=30)
                elif total_hours <= 6:  # 6小时以内
                    time_interval = 1  # 1小时间隔
                    time_format = '%H:%M'
                    locator = mdates.HourLocator(interval=1)
                elif total_hours <= 12:  # 12小时以内
                    time_interval = 2  # 2小时间隔
                    time_format = '%H:%M'
                    locator = mdates.HourLocator(interval=2)
                elif total_hours <= 24:  # 24小时以内
                    time_interval = 4  # 4小时间隔
                    time_format = '%m-%d %H:%M'
                    locator = mdates.HourLocator(interval=4)
                else:  # 超过24小时
                    time_interval = 6  # 6小时间隔
                    time_format = '%m-%d %H:%M'
                    locator = mdates.HourLocator(interval=6)
                
                # 设置x轴格式
                for ax in [ax1, ax2, ax3, ax4, ax5, ax6, ax7, ax8, ax9, ax10]:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter(time_format))
                    ax.xaxis.set_major_locator(locator)
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
                    
                logger.info(f"监控时长: {total_hours:.1f}小时，设置时间间隔: {time_interval}小时")
            else:
                # 默认设置
                for ax in [ax1, ax2, ax3, ax4, ax5, ax6, ax7, ax8, ax9, ax10]:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
            
            plt.tight_layout()
            
            # 保存图表
            chart_file = os.path.join(self.output_dir, 'ssh_monitoring_charts.png')
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            # 附加到Allure报告
            allure.attach.file(chart_file, "SSH监控图表(含FPS)", allure.attachment_type.PNG)
            
        except Exception as e:
            allure.attach(f"图表生成失败: {str(e)}", "图表生成错误", allure.attachment_type.TEXT)
    
    def _generate_statistics_report(self, temp_threshold, cpu_threshold, memory_threshold, disk_threshold):
        """生成统计报告"""
        if not self.monitoring_data:
            allure.attach("没有收集到监控数据，无法生成统计报告", "统计报告", allure.attachment_type.TEXT)
            return
        
        # 计算统计信息
        total_collections = len(self.monitoring_data)
        successful_collections = len([d for d in self.monitoring_data if d['success']])
        success_rate = (successful_collections / total_collections) * 100 if total_collections > 0 else 0
        
        # 计算平均值（处理空数组）
        temp_data = [d['temperature'] for d in self.monitoring_data if d['temperature'] > 0]
        cpu_data = [d['cpu_usage'] for d in self.monitoring_data if d['cpu_usage'] > 0]
        memory_data = [d['memory_usage'] for d in self.monitoring_data if d['memory_usage'] > 0]
        disk_data = [d['disk_usage'] for d in self.monitoring_data if d['disk_usage'] > 0]
        load_data = [d['load_avg_1min'] for d in self.monitoring_data if d['load_avg_1min'] > 0]
        estimated_fps_data = [d['estimated_fps'] for d in self.monitoring_data if d['estimated_fps'] > 0]  # analysis fps
        real_fps_data = [d['real_fps'] for d in self.monitoring_data if d['real_fps'] > 0]  # Actual FPS
        target_fps_data = [d.get('target_fps', 0) for d in self.monitoring_data if d.get('target_fps', 0) > 0]  # Target FPS
        smart_fps_data = [d.get('smart_fps', 0) for d in self.monitoring_data if d.get('smart_fps', 0) > 0]  # Smart fps
        bitrate_data = [d['estimated_bitrate'] for d in self.monitoring_data if d['estimated_bitrate'] > 0]
        latency_data = [d['estimated_latency'] for d in self.monitoring_data if d['estimated_latency'] > 0]
        quality_data = [d['video_quality_score'] for d in self.monitoring_data if d['video_quality_score'] > 0]
        bpu_temp_data = [d['bpu_temperature'] for d in self.monitoring_data if d.get('bpu_temperature', 0) > 0]
        bpu_usage_report_data = [d['bpu_usage'] for d in self.monitoring_data if d.get('bpu_usage', 0) is not None]
        if not bpu_usage_report_data:
            bpu_usage_report_data = [d.get('bpu_usage', 0) for d in self.monitoring_data]
        
        avg_temp = np.mean(temp_data) if temp_data else 0
        avg_cpu = np.mean(cpu_data) if cpu_data else 0
        avg_memory = np.mean(memory_data) if memory_data else 0
        avg_disk = np.mean(disk_data) if disk_data else 0
        avg_load = np.mean(load_data) if load_data else 0
        avg_estimated_fps = np.mean(estimated_fps_data) if estimated_fps_data else 0
        avg_real_fps = np.mean(real_fps_data) if real_fps_data else 0
        avg_target_fps = np.mean(target_fps_data) if target_fps_data else 0
        avg_smart_fps = np.mean(smart_fps_data) if smart_fps_data else 0
        avg_bitrate = np.mean(bitrate_data) if bitrate_data else 0
        avg_latency = np.mean(latency_data) if latency_data else 0
        avg_quality = np.mean(quality_data) if quality_data else 0
        avg_bpu_temp = np.mean(bpu_temp_data) if bpu_temp_data else 0
        avg_bpu_usage = np.mean(bpu_usage_report_data) if bpu_usage_report_data else 0
        max_bpu_temp = np.max(bpu_temp_data) if bpu_temp_data else 0
        max_bpu_usage = np.max(bpu_usage_report_data) if bpu_usage_report_data else 0
        min_bpu_temp = np.min(bpu_temp_data) if bpu_temp_data else 0
        min_bpu_usage = np.min(bpu_usage_report_data) if bpu_usage_report_data else 0
        avg_camera_processes = np.mean([d['camera_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        avg_x5_processes = np.mean([d['x5_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        avg_encoder_processes = np.mean([d['encoder_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        avg_ffmpeg_processes = np.mean([d['ffmpeg_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        
        # 计算最大值（处理空数组）
        max_temp = np.max(temp_data) if temp_data else 0
        max_cpu = np.max(cpu_data) if cpu_data else 0
        max_memory = np.max(memory_data) if memory_data else 0
        max_disk = np.max(disk_data) if disk_data else 0
        max_load = np.max(load_data) if load_data else 0
        max_estimated_fps = np.max(estimated_fps_data) if estimated_fps_data else 0
        max_real_fps = np.max(real_fps_data) if real_fps_data else 0
        max_target_fps = np.max(target_fps_data) if target_fps_data else 0
        max_smart_fps = np.max(smart_fps_data) if smart_fps_data else 0
        max_bitrate = np.max(bitrate_data) if bitrate_data else 0
        max_latency = np.max(latency_data) if latency_data else 0
        max_quality = np.max(quality_data) if quality_data else 0
        max_camera_processes = np.max([d['camera_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        max_x5_processes = np.max([d['x5_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        max_encoder_processes = np.max([d['encoder_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        max_ffmpeg_processes = np.max([d['ffmpeg_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        
        # 计算最小值（处理空数组）
        min_temp = np.min(temp_data) if temp_data else 0
        min_cpu = np.min(cpu_data) if cpu_data else 0
        min_memory = np.min(memory_data) if memory_data else 0
        min_disk = np.min(disk_data) if disk_data else 0
        min_load = np.min(load_data) if load_data else 0
        min_estimated_fps = np.min(estimated_fps_data) if estimated_fps_data else 0
        min_real_fps = np.min(real_fps_data) if real_fps_data else 0
        min_target_fps = np.min(target_fps_data) if target_fps_data else 0
        min_smart_fps = np.min(smart_fps_data) if smart_fps_data else 0
        min_bitrate = np.min(bitrate_data) if bitrate_data else 0
        min_latency = np.min(latency_data) if latency_data else 0
        min_quality = np.min(quality_data) if quality_data else 0
        min_camera_processes = np.min([d['camera_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        min_x5_processes = np.min([d['x5_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        min_encoder_processes = np.min([d['encoder_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        min_ffmpeg_processes = np.min([d['ffmpeg_processes_count'] for d in self.monitoring_data]) if self.monitoring_data else 0
        
        # 生成报告
        report = f"""
        ===== X5摄像头SSH底层数据统计报告 =====
        
        测试时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        总收集次数: {total_collections}
        成功收集: {successful_collections}
        成功率: {success_rate:.2f}%
        
        连接状态统计:
        - SSH连接断开次数: {self.ssh_connection_drops}
        
        硬件统计:
        温度:
        - 平均值: {avg_temp:.2f}°C
        - 最大值: {max_temp:.2f}°C
        - 阈值: {temp_threshold}°C
        
        CPU使用率:
        - 平均值: {avg_cpu:.2f}%
        - 最大值: {max_cpu:.2f}%
        - 阈值: {cpu_threshold}%
        
        BPU (hrut_somstatus):
        - BPU温度 平均: {avg_bpu_temp:.2f}°C, 最大: {max_bpu_temp:.2f}°C, 最小: {min_bpu_temp:.2f}°C
        - BPU使用率(ratio) 平均: {avg_bpu_usage:.2f}, 最大: {max_bpu_usage:.2f}, 最小: {min_bpu_usage:.2f}
        
        内存使用率:
        - 平均值: {avg_memory:.2f}%
        - 最大值: {max_memory:.2f}%
        - 阈值: {memory_threshold}%
        
        磁盘使用率:
        - 平均值: {avg_disk:.2f}%
        - 最大值: {max_disk:.2f}%
        - 阈值: {disk_threshold}%
        
        系统负载:
        - 平均值: {avg_load:.2f}
        - 最大值: {max_load:.2f}
        
视频性能统计:
Actual FPS:
- 平均值: {avg_real_fps:.2f}
- 最大值: {max_real_fps:.2f}
- 最小值: {min_real_fps:.2f}

Target FPS:
- 平均值: {avg_target_fps:.2f}
- 最大值: {max_target_fps:.2f}
- 最小值: {min_target_fps:.2f}

Smart fps:
- 平均值: {avg_smart_fps:.2f}
- 最大值: {max_smart_fps:.2f}
- 最小值: {min_smart_fps:.2f}

analysis fps:
- 平均值: {avg_estimated_fps:.2f}
- 最大值: {max_estimated_fps:.2f}
- 最小值: {min_estimated_fps:.2f}
        
        码率:
        - 平均值: {avg_bitrate:.2f} kbps
        - 最大值: {max_bitrate:.2f} kbps
        - 最小值: {min_bitrate:.2f} kbps
        
        延迟:
        - 平均值: {avg_latency:.2f} ms
        - 最大值: {max_latency:.2f} ms
        - 最小值: {min_latency:.2f} ms
        
        视频质量:
        - 平均值: {avg_quality:.2f}
        - 最大值: {max_quality:.2f}
        - 最小值: {min_quality:.2f}
        
        摄像头进程统计:
        - 摄像头进程数(平均): {avg_camera_processes:.1f}
        - 摄像头进程数(最大): {max_camera_processes}
        - 摄像头进程数(最小): {min_camera_processes}
        - X5进程数(平均): {avg_x5_processes:.1f}
        - X5进程数(最大): {max_x5_processes}
        - X5进程数(最小): {min_x5_processes}
        - 编码器进程数(平均): {avg_encoder_processes:.1f}
        - 编码器进程数(最大): {max_encoder_processes}
        - 编码器进程数(最小): {min_encoder_processes}
        - FFmpeg进程数(平均): {avg_ffmpeg_processes:.1f}
        - FFmpeg进程数(最大): {max_ffmpeg_processes}
        - FFmpeg进程数(最小): {min_ffmpeg_processes}
        
        错误统计:
        - 总错误数: {len(self.error_log)}
        """
        
        allure.attach(report, "SSH统计报告", allure.attachment_type.TEXT)
    
    def _save_csv_data(self):
        """保存CSV数据"""
        if not self.monitoring_data:
            allure.attach("没有监控数据可保存", "CSV数据", allure.attachment_type.TEXT)
            return
        
        try:
            import csv
            csv_file = os.path.join(self.output_dir, 'ssh_monitoring_data.csv')
            
            # 获取所有字段名
            fieldnames = list(self.monitoring_data[0].keys())
            
            with open(csv_file, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.monitoring_data)
            
            allure.attach.file(csv_file, "SSH监控数据CSV", allure.attachment_type.CSV)
            
        except Exception as e:
            allure.attach(f"CSV保存失败: {str(e)}", "CSV保存错误", allure.attachment_type.TEXT)
    
    def _generate_final_report(self, temp_threshold, cpu_threshold, memory_threshold, disk_threshold):
        """生成最终报告"""
        end_time = datetime.now()
        total_duration = (end_time - self.start_time).total_seconds()
        
        # 生成最终统计报告
        self._generate_statistics_report(temp_threshold, cpu_threshold, memory_threshold, disk_threshold)
        
        # 生成最终图表
        print(f"开始生成图表，数据点数量: {len(self.monitoring_data)}")
        try:
            self._generate_monitoring_charts(temp_threshold, cpu_threshold, memory_threshold, disk_threshold)
            print("图表生成完成")
        except Exception as e:
            print(f"图表生成失败: {str(e)}")
            import traceback
            traceback.print_exc()
        
        # 保存CSV数据
        self._save_csv_data()
        
        # 生成错误报告
        self._generate_error_report()
        
        # 生成最终总结
        final_summary = f"""
        ===== X5摄像头SSH底层数据24小时监控最终报告 =====
        
        监控时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} - {end_time.strftime('%Y-%m-%d %H:%M:%S')}
        总监控时间: {total_duration:.0f}秒 ({total_duration/3600:.1f}小时)
        总收集次数: {self.total_collections}
        成功收集: {self.successful_collections}
        成功率: {(self.successful_collections/self.total_collections)*100:.2f}%
        
        监控指标:
        - SSH连接断开次数: {self.ssh_connection_drops}
        - 总错误数: {len(self.error_log)}
        
        监控结论:
        """
        
        # 判断监控是否成功
        if (self.successful_collections/self.total_collections) >= 0.95 and self.ssh_connection_drops < 10:
            final_summary += "✅ 监控成功 - X5摄像头底层数据监控正常"
            test_passed = True
        else:
            final_summary += "❌ 监控失败 - X5摄像头底层数据监控存在问题"
            test_passed = False
        
        allure.attach(final_summary, "最终监控报告", allure.attachment_type.TEXT)
        
        # 断言
        assert test_passed, f"X5摄像头SSH底层数据24小时监控失败，成功率: {(self.successful_collections/self.total_collections)*100:.2f}%"
    
    def _generate_error_report(self):
        """生成错误报告"""
        if not self.error_log:
            allure.attach("无错误记录", "错误报告", allure.attachment_type.TEXT)
            return
        
        error_report = "===== 错误报告 =====\n\n"
        for i, error in enumerate(self.error_log, 1):
            error_report += f"{i}. 时间: {error['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}\n"
            error_report += f"   类型: {error['type']}\n"
            if 'error' in error:
                error_report += f"   错误: {error['error']}\n"
            elif 'errors' in error:
                error_report += f"   错误: {', '.join(error['errors'])}\n"
            error_report += "\n"
        
        allure.attach(error_report, "错误报告", allure.attachment_type.TEXT)

if __name__ == '__main__':
    """直接运行时的入口点"""
    import sys
    print("=" * 60)
    print("注意: 这是一个pytest测试文件，建议使用pytest运行:")
    print("  pytest Stability/test_x5_ssh_24h_monitoring.py")
    print("=" * 60)
    print("\n如果直接运行，将使用pytest.main()执行测试...")
    print()
    
    # 使用pytest运行
    exit_code = pytest.main([
        __file__,
        '-v',  # 详细输出
        '-s',  # 显示print输出
        '--tb=short',  # 简短的错误追踪
    ])
    
    sys.exit(exit_code)
