#!/usr/bin/env python3
# coding:utf-8
"""
@Time: 2025-01-28
@Author: gaoyuhang
@Description: X5摄像头AI模型性能测试脚本
@Purpose: 测试所有AI模型的加载和执行时间，评估性能表现
@Usage: python test_all_models_performance.py
"""

import paramiko
import re
import os
import json
import csv
import time
from datetime import datetime
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict
import yaml
import sys
from pathlib import Path

# 项目根目录(envloader.py 所在)加入 sys.path 以便复用统一凭据加载器
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)
import envloader  # noqa: E402

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

class ModelPerformanceTester:
    def __init__(self, ssh_config):
        """初始化模型性能测试器"""
        self.ssh_config = ssh_config
        self.ssh_client = None
        self.test_results = []
        performance_base_dir = os.path.join("allure-report", "model_performance")
        date_str = datetime.now().strftime('%Y%m%d')
        self.output_dir = os.path.join(performance_base_dir, date_str)
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        print(f"输出目录: {self.output_dir}")
    
    def connect_ssh(self):
        """建立SSH连接"""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            print(f"连接SSH: {self.ssh_config['host']}:{self.ssh_config['port']}")
            self.ssh_client.connect(
                hostname=self.ssh_config['host'],
                port=self.ssh_config['port'],
                username=self.ssh_config['username'],
                password=self.ssh_config['password'],
                timeout=self.ssh_config['timeout']
            )
            print("SSH连接成功！")
            return True
        except Exception as e:
            print(f"SSH连接失败: {str(e)}")
            return False
    
    def execute_command(self, command):
        """执行SSH命令"""
        try:
            if not self.ssh_client:
                return None
            
            stdin, stdout, stderr = self.ssh_client.exec_command(command)
            output = stdout.read().decode('utf-8').strip()
            error = stderr.read().decode('utf-8').strip()
            
            # 对于time命令，时间信息在stderr中
            if 'time ' in command:
                # 过滤掉chronyc警告，保留时间信息
                lines = error.split('\n')
                time_lines = [line for line in lines if not line.startswith('sh: line 1: chronyc: command not found')]
                error = '\n'.join(time_lines)
                
                # 显示时间同步警告（但不影响结果）
                chronyc_warnings = [line for line in lines if line.startswith('sh: line 1: chronyc: command not found')]
                if chronyc_warnings:
                    print(f"  时间同步警告: {len(chronyc_warnings)} 条警告")
            
            # 显示详细错误信息
            if error and 'chronyc: command not found' not in error:
                print(f"  命令错误: {error}")
            
            # 显示输出信息（用于调试）
            if output:
                print(f"  命令输出: {output[:200]}...")  # 只显示前200个字符
            
            # 对于time命令，返回stderr（包含时间信息）
            if 'time ' in command:
                return error if error else output
            else:
                return output
        except Exception as e:
            print(f"  命令执行异常: {str(e)}")
            return None
    
    def check_daemon_services(self):
        """检查daemon_services程序是否可用"""
        print("检查daemon_services程序...")
        
        # 检查程序是否存在
        check_command = "ls -la /userdata/deploy/body_solution/daemon_services"
        result = self.execute_command(check_command)
        
        if not result:
            print("  daemon_services程序不存在！")
            return False
        
        print(f"  daemon_services程序存在: {result}")
        
        # 检查程序帮助信息
        help_command = "/userdata/deploy/body_solution/daemon_services --help"
        help_result = self.execute_command(help_command)
        
        if help_result:
            print(f"  帮助信息: {help_result[:300]}...")
        else:
            print("  无法获取帮助信息")
        
        return True

    def discover_models(self):
        """发现所有可用的模型文件"""
        print("正在发现模型文件...")
        
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
            print(f"搜索路径: {path}")
            find_command = f"find {path} -name '*.bin' -type f 2>/dev/null"
            result = self.execute_command(find_command)
            
            if result:
                models = result.split('\n')
                for model in models:
                    if model.strip():
                        discovered_models.append(model.strip())
                        print(f"  发现: {model.strip()}")
        
        # 去重并排序
        self.model_paths = sorted(list(set(discovered_models)))
        print(f"总共发现 {len(self.model_paths)} 个模型文件")
        return self.model_paths
    
    def test_single_model(self, model_path):
        """测试单个模型的性能"""
        print(f"测试模型: {os.path.basename(model_path)}")
        
        # 构建测试命令
        test_command = f"time /userdata/deploy/body_solution/daemon_services --test-model {model_path}"
        
        # 执行测试命令
        result = self.execute_command(test_command)
        
        # 检查是否有有效的输出（包含时间信息）
        if not result or 'real\t' not in result:
            print(f"  模型测试失败: {model_path}")
            print(f"  命令: {test_command}")
            return None
        
        # 解析时间结果
        time_info = self.parse_time_output(result)
        
        if time_info and len(time_info) >= 3:  # 确保有real、user、sys三个时间
            # 获取模型信息
            model_info = self.get_model_info(model_path)
            
            test_result = {
                'model_path': model_path,
                'model_name': os.path.basename(model_path),
                'model_type': self.classify_model_type(model_path),
                'real_time': time_info.get('real', 0),
                'user_time': time_info.get('user', 0),
                'sys_time': time_info.get('sys', 0),
                'model_size': model_info.get('size', 0),
                'model_size_mb': model_info.get('size_mb', 0),
                'test_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'success'
            }
            
            print(f"  执行时间: {time_info.get('real', 0):.3f}s")
            return test_result
        else:
            print(f"  无法解析时间结果")
            return {
                'model_path': model_path,
                'model_name': os.path.basename(model_path),
                'model_type': self.classify_model_type(model_path),
                'real_time': 0,
                'user_time': 0,
                'sys_time': 0,
                'model_size': 0,
                'model_size_mb': 0,
                'test_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'failed'
            }
    
    def parse_time_output(self, output):
        """解析time命令的输出"""
        try:
            # 匹配time命令的输出格式
            # real	0m0.061s
            # user	0m0.051s
            # sys	0m0.009s
            time_pattern = r'(real|user|sys)\s+(\d+)m(\d+\.?\d*)s'
            matches = re.findall(time_pattern, output)
            
            time_info = {}
            for time_type, minutes, seconds in matches:
                total_seconds = int(minutes) * 60 + float(seconds)
                time_info[time_type] = total_seconds
            
            print(f"  解析时间结果: {time_info}")
            return time_info
        except Exception as e:
            print(f"  解析时间输出失败: {str(e)}")
            print(f"  原始输出: {output}")
            return None
    
    def get_model_info(self, model_path):
        """获取模型文件信息"""
        try:
            # 获取文件大小
            size_command = f"ls -la {model_path} | awk '{{print $5}}'"
            size_result = self.execute_command(size_command)
            model_size = int(size_result) if size_result and size_result.isdigit() else 0
            
            return {
                'size': model_size,
                'size_mb': round(model_size / (1024 * 1024), 2) if model_size > 0 else 0
            }
        except Exception as e:
            print(f"获取模型信息失败: {str(e)}")
            return {'size': 0, 'size_mb': 0}
    
    def classify_model_type(self, model_path):
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
    
    def generate_csv_report(self):
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
                    'model_size_mb': result.get('model_size_mb', 0),
                    'real_time': result['real_time'],
                    'user_time': result['user_time'],
                    'sys_time': result['sys_time'],
                    'test_time': result['test_time'],
                    'status': result['status']
                })
        
        print(f"CSV报告已生成: {csv_file}")
    
    def generate_charts(self):
        """生成性能测试图表"""
        if not self.test_results:
            print("没有测试结果，跳过图表生成")
            return
        
        # 过滤成功的测试结果
        success_results = [r for r in self.test_results if r['status'] == 'success']
        
        if not success_results:
            print("没有成功的测试结果，跳过图表生成")
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
        model_sizes = [r.get('model_size_mb', 0) for r in success_results]
        
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
        
        print(f"性能图表已生成: {chart_file}")
    
    def generate_statistics_report(self):
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
        
        print(f"统计报告已生成: {report_file}")
    
    def run_test(self):
        """运行完整的模型性能测试"""
        print("=" * 60)
        print("X5摄像头AI模型性能测试")
        print("=" * 60)
        
        # 1. 建立SSH连接
        if not self.connect_ssh():
            print("无法建立SSH连接，测试终止")
            return False
        
        try:
            # 2. 检查daemon_services程序
            if not self.check_daemon_services():
                print("daemon_services程序不可用，测试终止")
                return False
            
            # 3. 发现模型
            models = self.discover_models()
            if not models:
                print("未发现任何模型文件，测试终止")
                return False
            
            # 4. 测试所有模型
            print(f"\n开始测试 {len(models)} 个模型...")
            print("-" * 60)
            
            for i, model_path in enumerate(models, 1):
                print(f"[{i}/{len(models)}] 测试: {os.path.basename(model_path)}")
                result = self.test_single_model(model_path)
                if result:
                    self.test_results.append(result)
                print()
            
            # 5. 生成报告
            print("生成测试报告...")
            self.generate_csv_report()
            self.generate_charts()
            self.generate_statistics_report()
            
            # 6. 显示测试摘要
            success_count = len([r for r in self.test_results if r['status'] == 'success'])
            success_rate = success_count / len(self.test_results) * 100 if len(self.test_results) > 0 else 0
            
            print("\n" + "=" * 60)
            print("测试完成摘要")
            print("=" * 60)
            print(f"总模型数量: {len(self.test_results)}")
            print(f"成功测试: {success_count}")
            print(f"成功率: {success_rate:.1f}%")
            
            if success_count > 0:
                success_results = [r for r in self.test_results if r['status'] == 'success']
                avg_time = np.mean([r['real_time'] for r in success_results])
                print(f"平均执行时间: {avg_time:.3f}s")
            
            print(f"报告保存在: {self.output_dir}")
            print("=" * 60)
            
            return True
            
        finally:
            # 关闭SSH连接
            if self.ssh_client:
                self.ssh_client.close()
                print("SSH连接已关闭")

def main():
    """主函数"""
    # 加载配置文件
    project_root = Path(__file__).resolve().parents[1]  # 从 Performance/ 目录向上一级到项目根目录
    config_file = project_root / "config" / "test" / "camera.yaml"
    
    # 默认SSH配置
    ssh_host = '192.168.2.30'
    ssh_username = 'root'
    ssh_password = ''  # 不再预设默认口令, 缺失时下面直接报错
    ssh_port = 22
    ssh_timeout = 30
    
    # 尝试从配置文件加载(配置里凭据是 ${VAR} 占位符, 由 envloader 从 .env 展开)
    if config_file.exists():
        try:
            yaml_config = envloader.load_yaml(config_file)
            if yaml_config:
                ssh_host = yaml_config.get('ssh_host', ssh_host)
                ssh_username = yaml_config.get('ssh_username', ssh_username)
                ssh_password = yaml_config.get('ssh_password', ssh_password)
                ssh_port = int(yaml_config.get('ssh_port', ssh_port))
                ssh_timeout = int(yaml_config.get('ssh_timeout', ssh_timeout))
                print(f"✅ 已从配置文件加载 SSH 配置: {config_file}")
                print(f"   SSH Host: {ssh_host}")
                print(f"   SSH Username: {ssh_username}")
                print(f"   SSH Port: {ssh_port}")
        except Exception as e:
            print(f"⚠️  读取配置文件失败: {e}")
            print("   使用默认值或环境变量")
    else:
        print(f"⚠️  配置文件不存在: {config_file}")
        print("   使用默认值或环境变量")
    
    # 环境变量可以覆盖配置文件的值
    ssh_host = os.getenv('SSH_HOST', ssh_host)
    ssh_username = os.getenv('SSH_USERNAME', ssh_username)
    ssh_password = os.getenv('SSH_PASSWORD', ssh_password) or envloader.get('CAMERA_SSH_PASSWORD', '')
    ssh_port = int(os.getenv('SSH_PORT', ssh_port))
    ssh_timeout = int(os.getenv('SSH_TIMEOUT', ssh_timeout))

    if not ssh_password:
        raise SystemExit(
            "缺少 SSH 口令。请在项目根 .env 设置 CAMERA_SSH_PASSWORD, "
            "或通过环境变量 SSH_PASSWORD 注入。"
        )
    
    print("")
    
    # SSH连接配置
    ssh_config = {
        'host': ssh_host,
        'username': ssh_username,
        'password': ssh_password,
        'port': ssh_port,
        'timeout': ssh_timeout
    }
    
    # 创建测试器并运行测试
    tester = ModelPerformanceTester(ssh_config)
    success = tester.run_test()
    
    if success:
        print("模型性能测试完成！")
    else:
        print("模型性能测试失败！")

if __name__ == "__main__":
    main()
