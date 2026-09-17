#!/usr/bin/env python 
# coding:utf-8
"""
@Time: 2025-01-28
@Author: gaoyuhang
@Description: X5摄像头AI模型性能测试
@Purpose: 测试所有AI模型的加载和执行时间，评估性能表现
@Features: 
- 通过SSH连接测试所有模型
- 测量模型加载和执行时间
- 生成性能测试报告
- 支持多种模型类型测试
"""

import allure
import pytest
import time
import json
import csv
import os
import paramiko
import re
import threading
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import logging
import sys
from collections import defaultdict

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 配置控制台日志记录
def setup_console_logging():
    """设置控制台日志记录"""
    log_format = '%(asctime)s [%(filename)s:%(lineno)d] %(levelname)s: %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    logger = logging.getLogger('ModelPerformanceTest')
    logger.setLevel(logging.INFO)
    return logger

# 初始化日志
logger = setup_console_logging()

@allure.feature('x5-model-performance')
@allure.story('X5摄像头AI模型性能测试')
class TestModelPerformance(object):
    
    @pytest.fixture(scope="class", autouse=True)
    def prepare(self, request, env):
        """测试准备"""
        with allure.step("AI模型性能测试环境准备"):
            # SSH连接配置
            self.ssh_client = None
            self.env = env
            
            # 测试配置
            self.test_results = []
            self.model_paths = []
            self.performance_data = defaultdict(list)
            
            # 输出目录
            performance_base_dir = os.path.join("allure-report", "model_performance")
            date_str = datetime.now().strftime('%Y%m%d')
            self.output_dir = os.path.join(performance_base_dir, date_str)
            os.makedirs(self.output_dir, exist_ok=True)
            
            logger.info("AI模型性能测试环境准备完成")
    
    @pytest.fixture(scope="class", autouse=True)
    def teardown(self):
        """测试清理"""
        with allure.step("清理测试环境"):
            if self.ssh_client:
                self.ssh_client.close()
            logger.info("测试环境清理完成")
    
    def _connect_ssh(self):
        """建立SSH连接"""
        try:
            if self.ssh_client:
                # 测试连接是否仍然有效
                stdin, stdout, stderr = self.ssh_client.exec_command('echo "test"')
                stdout.read()
                return True
                
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            ssh_config = {
                'host': self.env.get('ssh_host', '192.168.2.119'),
                'username': self.env.get('ssh_username', 'root'),
                'password': self.env.get('ssh_password', 'root'),
                'port': self.env.get('ssh_port', 22),
                'timeout': self.env.get('ssh_timeout', 10)
            }
            
            logger.info(f"尝试SSH连接到: {ssh_config['host']}:{ssh_config['port']} (用户: {ssh_config['username']})")
            
            self.ssh_client.connect(
                hostname=ssh_config['host'],
                port=ssh_config['port'],
                username=ssh_config['username'],
                password=ssh_config['password'],
                timeout=ssh_config['timeout']
            )
            logger.info("SSH连接成功！")
            return True
        except Exception as e:
            logger.error(f"SSH连接失败: {str(e)}")
            self.ssh_client = None
            return False
    
    def _execute_ssh_command(self, command):
        """执行SSH命令"""
        try:
            if not self.ssh_client:
                return None
            
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            if error:
                logger.warning(f"命令执行警告: {error}")
            
            return output
        except Exception as e:
            logger.error(f"命令执行失败: {str(e)}")
            return None
    
    def _discover_models(self):
        """发现所有可用的模型文件"""
        with allure.step("发现可用模型文件"):
            logger.info("开始发现模型文件...")
            
            # 模型搜索路径
            model_paths = [
                "/userdata/deploy/body_solution/",
                "/userdata/deploy/models/",
                "/userdata/deploy/ai_models/",
                "/app/models/",
                "/userdata/models/"
            ]
            
            discovered_models = []
            
            for path in model_paths:
                logger.info(f"搜索路径: {path}")
                
                # 查找所有.bin文件
                find_command = f"find {path} -name '*.bin' -type f 2>/dev/null"
                result = self._execute_ssh_command(find_command)
                
                if result:
                    models = result.split('\n')
                    for model in models:
                        if model.strip():
                            discovered_models.append(model.strip())
                            logger.info(f"发现模型: {model.strip()}")
            
            # 去重并排序
            self.model_paths = sorted(list(set(discovered_models)))
            logger.info(f"总共发现 {len(self.model_paths)} 个模型文件")
            
            return self.model_paths
    
    def _test_single_model(self, model_path):
        """测试单个模型的性能"""
        logger.info(f"开始测试模型: {model_path}")
        
        # 构建测试命令
        test_command = f"time /userdata/deploy/body_solution/daemon_services --test-model {model_path}"
        
        # 执行测试命令
        result = self._execute_ssh_command(test_command)
        
        if not result:
            logger.error(f"模型测试失败: {model_path}")
            return None
        
        # 解析时间结果
        time_info = self._parse_time_output(result)
        
        if time_info:
            # 获取模型信息
            model_info = self._get_model_info(model_path)
            
            test_result = {
                'model_path': model_path,
                'model_name': os.path.basename(model_path),
                'model_type': self._classify_model_type(model_path),
                'real_time': time_info.get('real', 0),
                'user_time': time_info.get('user', 0),
                'sys_time': time_info.get('sys', 0),
                'model_size': model_info.get('size', 0),
                'test_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'success'
            }
            
            logger.info(f"模型测试成功: {model_path} - 执行时间: {time_info.get('real', 0)}s")
            return test_result
        else:
            logger.error(f"无法解析时间结果: {model_path}")
            return {
                'model_path': model_path,
                'model_name': os.path.basename(model_path),
                'model_type': self._classify_model_type(model_path),
                'real_time': 0,
                'user_time': 0,
                'sys_time': 0,
                'model_size': 0,
                'test_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'failed'
            }
    
    def _parse_time_output(self, output):
        """解析time命令的输出"""
        try:
            # 匹配time命令的输出格式
            # real    0m0.071s
            # user    0m0.054s
            # sys     0m0.011s
            time_pattern = r'(real|user|sys)\s+(\d+)m(\d+\.?\d*)s'
            matches = re.findall(time_pattern, output)
            
            time_info = {}
            for time_type, minutes, seconds in matches:
                total_seconds = int(minutes) * 60 + float(seconds)
                time_info[time_type] = total_seconds
            
            return time_info
        except Exception as e:
            logger.error(f"解析时间输出失败: {str(e)}")
            return None
    
    def _get_model_info(self, model_path):
        """获取模型文件信息"""
        try:
            # 获取文件大小
            size_command = f"ls -la {model_path} | awk '{{print $5}}'"
            size_result = self._execute_ssh_command(size_command)
            model_size = int(size_result) if size_result and size_result.isdigit() else 0
            
            return {
                'size': model_size,
                'size_mb': round(model_size / (1024 * 1024), 2) if model_size > 0 else 0
            }
        except Exception as e:
            logger.error(f"获取模型信息失败: {str(e)}")
            return {'size': 0, 'size_mb': 0}
    
    def _classify_model_type(self, model_path):
        """根据路径和文件名分类模型类型"""
        model_name = os.path.basename(model_path).lower()
        
        if 'yolo' in model_name:
            if 'v8' in model_name:
                return 'YOLO v8'
            elif 'v11' in model_name:
                return 'YOLO v11'
            else:
                return 'YOLO'
        elif 'pose' in model_name:
            return 'Pose Detection'
        elif 'face' in model_name:
            return 'Face Detection'
        elif 'body' in model_name:
            return 'Body Detection'
        elif 'race' in model_name:
            return 'Race Analysis'
        elif 'item' in model_name:
            return 'Item Detection'
        else:
            return 'Unknown'
    
    def _generate_performance_report(self):
        """生成性能测试报告"""
        with allure.step("生成性能测试报告"):
            logger.info("开始生成性能测试报告...")
            
            # 生成CSV报告
            self._generate_csv_report()
            
            # 生成图表
            self._generate_performance_charts()
            
            # 生成统计报告
            self._generate_statistics_report()
            
            logger.info("性能测试报告生成完成")
    
    def _generate_csv_report(self):
        """生成CSV格式的测试报告"""
        csv_file = os.path.join(self.output_dir, 'model_performance_report.csv')
        
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            fieldnames = [
                'model_name', 'model_type', 'model_path', 'model_size_mb',
                'real_time', 'user_time', 'sys_time', 'test_time', 'status'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.test_results:
                writer.writerow({
                    'model_name': result['model_name'],
                    'model_type': result['model_type'],
                    'model_path': result['model_path'],
                    'model_size_mb': result.get('model_size', {}).get('size_mb', 0),
                    'real_time': result['real_time'],
                    'user_time': result['user_time'],
                    'sys_time': result['sys_time'],
                    'test_time': result['test_time'],
                    'status': result['status']
                })
        
        logger.info(f"CSV报告已生成: {csv_file}")
    
    def _generate_performance_charts(self):
        """生成性能测试图表"""
        if not self.test_results:
            logger.warning("没有测试结果，跳过图表生成")
            return
        
        # 过滤成功的测试结果
        success_results = [r for r in self.test_results if r['status'] == 'success']
        
        if not success_results:
            logger.warning("没有成功的测试结果，跳过图表生成")
            return
        
        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('X5摄像头AI模型性能测试报告', fontsize=16, fontweight='bold')
        
        # 1. 模型执行时间对比
        ax1 = axes[0, 0]
        model_names = [r['model_name'] for r in success_results]
        real_times = [r['real_time'] for r in success_results]
        
        bars = ax1.bar(range(len(model_names)), real_times, color='skyblue', alpha=0.7)
        ax1.set_title('模型执行时间对比', fontweight='bold')
        ax1.set_xlabel('模型名称')
        ax1.set_ylabel('执行时间 (秒)')
        ax1.set_xticks(range(len(model_names)))
        ax1.set_xticklabels(model_names, rotation=45, ha='right')
        
        # 添加数值标签
        for i, bar in enumerate(bars):
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height + 0.001,
                    f'{height:.3f}s', ha='center', va='bottom', fontsize=8)
        
        # 2. 模型类型性能对比
        ax2 = axes[0, 1]
        model_types = defaultdict(list)
        for r in success_results:
            model_types[r['model_type']].append(r['real_time'])
        
        type_names = list(model_types.keys())
        type_avg_times = [np.mean(times) for times in model_types.values()]
        
        bars2 = ax2.bar(type_names, type_avg_times, color='lightgreen', alpha=0.7)
        ax2.set_title('模型类型平均执行时间', fontweight='bold')
        ax2.set_xlabel('模型类型')
        ax2.set_ylabel('平均执行时间 (秒)')
        ax2.tick_params(axis='x', rotation=45)
        
        # 添加数值标签
        for i, bar in enumerate(bars2):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height + 0.001,
                    f'{height:.3f}s', ha='center', va='bottom', fontsize=8)
        
        # 3. 模型大小与执行时间关系
        ax3 = axes[1, 0]
        model_sizes = [r.get('model_size', {}).get('size_mb', 0) for r in success_results]
        
        scatter = ax3.scatter(model_sizes, real_times, alpha=0.7, s=100, c='red')
        ax3.set_title('模型大小与执行时间关系', fontweight='bold')
        ax3.set_xlabel('模型大小 (MB)')
        ax3.set_ylabel('执行时间 (秒)')
        
        # 添加趋势线
        if len(model_sizes) > 1:
            z = np.polyfit(model_sizes, real_times, 1)
            p = np.poly1d(z)
            ax3.plot(model_sizes, p(model_sizes), "r--", alpha=0.8)
        
        # 4. CPU使用率分析
        ax4 = axes[1, 1]
        cpu_usage = [(r['user_time'] + r['sys_time']) / r['real_time'] * 100 
                    if r['real_time'] > 0 else 0 for r in success_results]
        
        bars4 = ax4.bar(range(len(model_names)), cpu_usage, color='orange', alpha=0.7)
        ax4.set_title('模型CPU使用率', fontweight='bold')
        ax4.set_xlabel('模型名称')
        ax4.set_ylabel('CPU使用率 (%)')
        ax4.set_xticks(range(len(model_names)))
        ax4.set_xticklabels(model_names, rotation=45, ha='right')
        
        # 添加数值标签
        for i, bar in enumerate(bars4):
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height + 1,
                    f'{height:.1f}%', ha='center', va='bottom', fontsize=8)
        
        plt.tight_layout()
        
        # 保存图表
        chart_file = os.path.join(self.output_dir, 'model_performance_charts.png')
        plt.savefig(chart_file, dpi=300, bbox_inches='tight')
        plt.close()
        
        logger.info(f"性能图表已生成: {chart_file}")
    
    def _generate_statistics_report(self):
        """生成统计报告"""
        if not self.test_results:
            return
        
        success_results = [r for r in self.test_results if r['status'] == 'success']
        failed_results = [r for r in self.test_results if r['status'] == 'failed']
        
        report_file = os.path.join(self.output_dir, 'model_performance_statistics.txt')
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("X5摄像头AI模型性能测试统计报告\n")
            f.write("=" * 50 + "\n\n")
            
            f.write(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"总模型数量: {len(self.test_results)}\n")
            f.write(f"成功测试: {len(success_results)}\n")
            f.write(f"失败测试: {len(failed_results)}\n")
            f.write(f"成功率: {len(success_results)/len(self.test_results)*100:.1f}%\n\n")
            
            if success_results:
                real_times = [r['real_time'] for r in success_results]
                user_times = [r['user_time'] for r in success_results]
                sys_times = [r['sys_time'] for r in success_results]
                
                f.write("执行时间统计:\n")
                f.write(f"  平均执行时间: {np.mean(real_times):.3f}s\n")
                f.write(f"  最快执行时间: {np.min(real_times):.3f}s\n")
                f.write(f"  最慢执行时间: {np.max(real_times):.3f}s\n")
                f.write(f"  执行时间标准差: {np.std(real_times):.3f}s\n\n")
                
                f.write("CPU使用率统计:\n")
                cpu_usage = [(r['user_time'] + r['sys_time']) / r['real_time'] * 100 
                           if r['real_time'] > 0 else 0 for r in success_results]
                f.write(f"  平均CPU使用率: {np.mean(cpu_usage):.1f}%\n")
                f.write(f"  最高CPU使用率: {np.max(cpu_usage):.1f}%\n")
                f.write(f"  最低CPU使用率: {np.min(cpu_usage):.1f}%\n\n")
                
                # 按模型类型统计
                model_types = defaultdict(list)
                for r in success_results:
                    model_types[r['model_type']].append(r['real_time'])
                
                f.write("按模型类型统计:\n")
                for model_type, times in model_types.items():
                    f.write(f"  {model_type}:\n")
                    f.write(f"    数量: {len(times)}\n")
                    f.write(f"    平均时间: {np.mean(times):.3f}s\n")
                    f.write(f"    最快时间: {np.min(times):.3f}s\n")
                    f.write(f"    最慢时间: {np.max(times):.3f}s\n\n")
            
            if failed_results:
                f.write("失败模型列表:\n")
                for result in failed_results:
                    f.write(f"  - {result['model_name']} ({result['model_path']})\n")
        
        logger.info(f"统计报告已生成: {report_file}")
    
    @allure.story('AI模型性能测试')
    def test_model_performance(self):
        """测试所有AI模型的性能"""
        with allure.step("建立SSH连接"):
            if not self._connect_ssh():
                pytest.fail("无法建立SSH连接")
        
        with allure.step("发现可用模型"):
            models = self._discover_models()
            if not models:
                pytest.fail("未发现任何模型文件")
            
            allure.attach(
                json.dumps(models, indent=2, ensure_ascii=False),
                "发现的模型文件列表",
                allure.attachment_type.JSON
            )
        
        with allure.step("执行模型性能测试"):
            logger.info(f"开始测试 {len(models)} 个模型...")
            
            for i, model_path in enumerate(models, 1):
                logger.info(f"测试进度: {i}/{len(models)} - {model_path}")
                
                with allure.step(f"测试模型 {i}/{len(models)}: {os.path.basename(model_path)}"):
                    result = self._test_single_model(model_path)
                    if result:
                        self.test_results.append(result)
                        
                        # 记录测试结果
                        allure.attach(
                            json.dumps(result, indent=2, ensure_ascii=False),
                            f"模型测试结果: {result['model_name']}",
                            allure.attachment_type.JSON
                        )
        
        with allure.step("生成性能测试报告"):
            self._generate_performance_report()
            
            # 附加报告文件
            if os.path.exists(os.path.join(self.output_dir, 'model_performance_report.csv')):
                allure.attach.file(
                    os.path.join(self.output_dir, 'model_performance_report.csv'),
                    "模型性能测试CSV报告",
                    allure.attachment_type.CSV
                )
            
            if os.path.exists(os.path.join(self.output_dir, 'model_performance_charts.png')):
                allure.attach.file(
                    os.path.join(self.output_dir, 'model_performance_charts.png'),
                    "模型性能测试图表",
                    allure.attachment_type.PNG
                )
            
            if os.path.exists(os.path.join(self.output_dir, 'model_performance_statistics.txt')):
                allure.attach.file(
                    os.path.join(self.output_dir, 'model_performance_statistics.txt'),
                    "模型性能测试统计报告",
                    allure.attachment_type.TEXT
                )
        
        # 验证测试结果
        assert len(self.test_results) > 0, "没有成功测试任何模型"
        
        success_count = len([r for r in self.test_results if r['status'] == 'success'])
        success_rate = success_count / len(self.test_results) * 100
        
        logger.info(f"测试完成: 成功 {success_count}/{len(self.test_results)} ({success_rate:.1f}%)")
        
        # 生成测试摘要
        allure.attach(
            f"测试摘要:\n"
            f"- 总模型数量: {len(self.test_results)}\n"
            f"- 成功测试: {success_count}\n"
            f"- 成功率: {success_rate:.1f}%\n"
            f"- 平均执行时间: {np.mean([r['real_time'] for r in self.test_results if r['status'] == 'success']):.3f}s",
            "测试摘要",
            allure.attachment_type.TEXT
        )
