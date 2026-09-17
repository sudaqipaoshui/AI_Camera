#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X5摄像头SSH监控测试运行器
按顺序执行：
1. test_x5_ssh_24h_monitoring.py - 执行24小时监控测试
2. smart_csv_fixer.py - 修复生成的CSV文件
3. generate_report_from_csv.py - 生成监控报告和图表
"""

import pytest
import sys
import os
import glob
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
STABILITY_DIR = Path(__file__).parent


def find_latest_csv():
    """查找最新的CSV文件"""
    pattern = str(PROJECT_ROOT / "allure-report" / "24h-monitoring" / "*" / "ssh_monitoring_data.csv")
    csv_files = glob.glob(pattern)
    
    if not csv_files:
        pattern = str(PROJECT_ROOT / "allure-report" / "*" / "ssh_monitoring_data.csv")
        csv_files = glob.glob(pattern)
    
    if csv_files:
        csv_files.sort(key=os.path.getmtime, reverse=True)
        return csv_files[0]
    return None


class TestX5MonitoringRunner(object):
    """X5摄像头SSH监控测试运行器"""
    
    def test_execute_monitoring(self):
        """步骤1: 执行24小时监控测试"""
        print("\n" + "=" * 60)
        print("步骤1: 执行24小时监控测试")
        print("=" * 60)
        
        test_file = STABILITY_DIR / "test_x5_ssh_24h_monitoring.py"
        
        if not test_file.exists():
            pytest.skip(f"测试文件不存在: {test_file}")
        # 使用 subprocess 避免 allure 上下文冲突
        import subprocess
        result = subprocess.run([
            sys.executable,
            '-m', 'pytest',
            str(test_file),
            '-v',
            '-s',
            '--tb=short',
            '-m', 'x5_ssh_24h_monitoring'
        ], capture_output=False, text=True)
        
        if result.returncode != 0:
            pytest.fail(f"监控测试失败，退出码: {result.returncode}")
        
        print("\n✅ 步骤1完成: 监控测试执行成功")
    
    def test_fixed_csv_file(self):
        """步骤2: 修复生成的CSV文件"""
        print("\n" + "=" * 60)
        print("步骤2: 修复CSV文件")
        print("=" * 60)
        
        csv_file = find_latest_csv()
        if not csv_file:
            pytest.skip("未找到CSV文件，请先执行监控测试")
        
        print(f"找到CSV文件: {csv_file}")
        
        sys.path.insert(0, str(STABILITY_DIR))
        from smart_csv_fixer import SmartCSVFixer
        
        fixer = SmartCSVFixer(csv_file)
        if not fixer.auto_fix():
            pytest.fail("CSV文件修复失败")
        
        print(f"\n✅ 步骤2完成: CSV文件修复成功 - {csv_file}")
    
    def test_generate_report(self):
        """步骤3: 生成监控报告和图表"""
        print("\n" + "=" * 60)
        print("步骤3: 生成监控报告和图表")
        print("=" * 60)
        
        csv_file = find_latest_csv()
        if not csv_file:
            pytest.skip("未找到CSV文件，请先执行监控测试和CSV修复")
        
        if not os.path.exists(csv_file):
            pytest.fail(f"CSV文件不存在: {csv_file}")
        
        print(f"使用CSV文件: {csv_file}")
        
        sys.path.insert(0, str(STABILITY_DIR))
        from generate_report_from_csv import X5MonitoringReportGenerator
        
        output_dir = os.path.dirname(csv_file)
        generator = X5MonitoringReportGenerator(csv_file, output_dir)
        generator.generate_all_reports()
        
        print(f"\n✅ 步骤3完成: 报告已生成 - {output_dir}")
