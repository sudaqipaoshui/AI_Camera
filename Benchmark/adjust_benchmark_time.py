#!/usr/bin/env python3
"""
快速调整基准测试时间参数
"""

import sys
from benchmark_time_config import BenchmarkTimeConfig, QuickTestConfig, StandardTestConfig, ExtendedTestConfig, StressTestConfig

def update_benchmark_script(config, script_file):
    """更新基准测试脚本中的时间参数"""
    try:
        with open(script_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 更新CPU测试时间
        content = content.replace(
            f'stress-ng --cpu 8 --timeout 60s',
            f'stress-ng --cpu 8 --timeout {config.cpu_stress_duration}s'
        )
        content = content.replace(
            f'sleep 60',
            f'sleep {config.cpu_dd_sleep}'
        )
        
        # 更新NPU测试轮数
        content = content.replace(
            f'for i in $(seq 1 20); do',
            f'for i in $(seq 1 {config.npu_test_rounds}); do'
        )
        
        # 更新视频流测试时间
        content = content.replace(
            f'DURATION=60',
            f'DURATION={config.video_stream_duration}'
        )
        
        # 更新SSH超时时间
        content = content.replace(
            f'timeout=600',
            f'timeout={config.command_timeout}'
        )
        
        with open(script_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"✅ 已更新 {script_file}")
        return True
        
    except Exception as e:
        print(f"❌ 更新 {script_file} 失败: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("用法: python3 adjust_benchmark_time.py <配置类型>")
        print("配置类型:")
        print("  quick     - 快速测试 (5分钟)")
        print("  standard  - 标准测试 (15分钟)")
        print("  extended  - 扩展测试 (30分钟)")
        print("  stress    - 压力测试 (60分钟)")
        print("  custom    - 自定义配置")
        return
    
    config_type = sys.argv[1].lower()
    
    # 选择配置
    if config_type == "quick":
        config = QuickTestConfig()
    elif config_type == "standard":
        config = StandardTestConfig()
    elif config_type == "extended":
        config = ExtendedTestConfig()
    elif config_type == "stress":
        config = StressTestConfig()
    elif config_type == "custom":
        config = BenchmarkTimeConfig()
        print("自定义配置模式 - 请输入参数:")
        try:
            config.cpu_stress_duration = int(input(f"CPU压力测试时间 (当前: {config.cpu_stress_duration}秒): ") or config.cpu_stress_duration)
            config.npu_test_rounds = int(input(f"NPU测试轮数 (当前: {config.npu_test_rounds}轮): ") or config.npu_test_rounds)
            config.video_stream_duration = int(input(f"视频流测试时间 (当前: {config.video_stream_duration}秒): ") or config.video_stream_duration)
            config.command_timeout = int(input(f"命令超时时间 (当前: {config.command_timeout}秒): ") or config.command_timeout)
        except ValueError:
            print("❌ 输入格式错误，使用默认配置")
    else:
        print(f"❌ 未知配置类型: {config_type}")
        return
    
    print(f"\n=== 应用 {config_type.upper()} 配置 ===")
    config.print_config()
    
    # 更新脚本文件
    script_files = [
        "Benchmark/test_x5_benchmark_standalone.py"
    ]
    
    success_count = 0
    for script_file in script_files:
        if update_benchmark_script(config, script_file):
            success_count += 1
    
    print(f"\n✅ 成功更新 {success_count}/{len(script_files)} 个文件")
    print("\n💡 提示: 运行 'python3 test_x5_benchmark_standalone.py' 开始测试")

if __name__ == "__main__":
    main()


