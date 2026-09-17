#!/usr/bin/env python3
"""
X5基准测试时间配置
用于集中管理各种测试的时间参数
"""

class BenchmarkTimeConfig:
    """基准测试时间配置类"""
    
    def __init__(self):
        # SSH连接配置
        self.ssh_timeout = 30  # SSH连接超时时间（秒）
        self.command_timeout = 600  # 命令执行超时时间（秒）
        
        # CPU性能测试
        self.cpu_stress_duration = 60  # CPU压力测试持续时间（秒）
        self.cpu_dd_sleep = 60  # dd命令睡眠时间（秒）
        
        # NPU推理测试
        self.npu_test_rounds = 20  # NPU推理测试轮数
        self.npu_test_interval = 0.1  # 测试间隔（秒）- 基础配置使用短间隔
        
        # 内存带宽测试
        self.memory_test_size = 512  # 内存测试大小（MB）
        
        # 视频流测试
        self.video_stream_duration = 60  # 视频流测试持续时间（秒）
        self.video_stream_timeout = 5  # 视频流连接超时（秒）
        
        # 二阶段流水线测试
        self.pipeline_test_duration = 10  # 流水线测试持续时间（秒）
        
        # 报告生成
        self.report_generation_timeout = 30  # 报告生成超时（秒）
    
    def get_cpu_script_config(self):
        """获取CPU测试脚本配置"""
        return {
            'stress_ng_timeout': f"{self.cpu_stress_duration}s",
            'dd_sleep': self.cpu_dd_sleep,
            'cpu_cores': 8
        }
    
    def get_npu_script_config(self):
        """获取NPU测试脚本配置"""
        return {
            'test_rounds': self.npu_test_rounds,
            'test_interval': self.npu_test_interval
        }
    
    def get_video_script_config(self):
        """获取视频流测试脚本配置"""
        return {
            'duration': self.video_stream_duration,
            'timeout': self.video_stream_timeout
        }
    
    def get_ssh_config(self):
        """获取SSH配置"""
        return {
            'timeout': self.ssh_timeout,
            'command_timeout': self.command_timeout
        }
    
    def update_config(self, **kwargs):
        """更新配置参数"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                print(f"警告: 未知配置参数 {key}")
    
    def print_config(self):
        """打印当前配置"""
        print("=== 基准测试时间配置 ===")
        print(f"SSH连接超时: {self.ssh_timeout}秒")
        print(f"命令执行超时: {self.command_timeout}秒")
        print(f"CPU压力测试: {self.cpu_stress_duration}秒")
        print(f"NPU推理测试: {self.npu_test_rounds}轮")
        print(f"视频流测试: {self.video_stream_duration}秒")
        print(f"内存测试大小: {self.memory_test_size}MB")
        print("========================")

# 预定义配置方案
class QuickTestConfig(BenchmarkTimeConfig):
    """快速测试配置（5分钟）"""
    def __init__(self):
        super().__init__()
        self.cpu_stress_duration = 30
        self.cpu_dd_sleep = 30
        self.npu_test_rounds = 5
        self.video_stream_duration = 30
        self.pipeline_test_duration = 5

class StandardTestConfig(BenchmarkTimeConfig):
    """标准测试配置（15分钟）"""
    def __init__(self):
        super().__init__()
        # 调整为标准15分钟测试配置
        self.cpu_stress_duration = 300  # CPU压力测试5分钟
        self.cpu_dd_sleep = 300  # dd命令睡眠时间5分钟
        self.npu_test_rounds = 50  # NPU推理测试50轮
        self.npu_test_interval = 2.0  # NPU测试间隔2秒（50轮 × 2秒 = 100秒间隔 + 50轮 × 0.08秒 = 104秒 ≈ 1.7分钟）
        self.video_stream_duration = 180  # 视频流测试3分钟
        self.pipeline_test_duration = 90  # 流水线测试1.5分钟
        self.memory_test_size = 768  # 内存测试大小（增加测试时间）
        self.command_timeout = 1200  # 命令执行超时20分钟（确保充足时间）

class ExtendedTestConfig(BenchmarkTimeConfig):
    """扩展测试配置（30分钟）"""
    def __init__(self):
        super().__init__()
        self.cpu_stress_duration = 120
        self.cpu_dd_sleep = 120
        self.npu_test_rounds = 50
        self.video_stream_duration = 120
        self.pipeline_test_duration = 30
        self.memory_test_size = 1024

class StressTestConfig(BenchmarkTimeConfig):
    """压力测试配置（60分钟）"""
    def __init__(self):
        super().__init__()
        self.cpu_stress_duration = 300
        self.cpu_dd_sleep = 300
        self.npu_test_rounds = 100
        self.video_stream_duration = 300
        self.pipeline_test_duration = 60
        self.memory_test_size = 2048
        self.command_timeout = 1200

if __name__ == "__main__":
    # 示例用法
    config = BenchmarkTimeConfig()
    config.print_config()
    
    print("\n=== 快速测试配置 ===")
    quick_config = QuickTestConfig()
    quick_config.print_config()
    
    print("\n=== 扩展测试配置 ===")
    extended_config = ExtendedTestConfig()
    extended_config.print_config()


