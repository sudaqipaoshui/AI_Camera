#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基准测试报告清理工具
用于清理旧的、空的或重复的基准测试报告
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime, timedelta

def get_report_dirs():
    """获取所有基准测试报告目录"""
    report_base = Path("allure-report")
    benchmark_dir = report_base / "benchmark"
    
    if not benchmark_dir.exists():
        return []
    
    reports = []
    for item in benchmark_dir.iterdir():
        if item.is_dir():
            reports.append(item)
    
    return sorted(reports, key=lambda x: x.stat().st_mtime, reverse=True)

def count_files_in_dir(directory):
    """统计目录中的文件数量"""
    try:
        return len([f for f in directory.iterdir() if f.is_file()])
    except:
        return 0

def get_dir_size(directory):
    """获取目录大小"""
    total = 0
    try:
        for item in directory.rglob('*'):
            if item.is_file():
                total += item.stat().st_size
    except:
        pass
    return total

def cleanup_empty_reports(dry_run=True):
    """清理空报告目录"""
    reports = get_report_dirs()
    empty_reports = []
    
    for report_dir in reports:
        file_count = count_files_in_dir(report_dir)
        if file_count == 0:
            empty_reports.append(report_dir)
    
    if not empty_reports:
        print("✅ 没有找到空报告目录")
        return
    
    print(f"发现 {len(empty_reports)} 个空报告目录:")
    for report_dir in empty_reports:
        mtime = datetime.fromtimestamp(report_dir.stat().st_mtime)
        print(f"  - {report_dir.name} (创建于: {mtime.strftime('%Y-%m-%d %H:%M:%S')})")
    
    if dry_run:
        print("\n💡 使用 --delete 参数实际删除这些目录")
    else:
        print("\n🗑️  正在删除空报告目录...")
        for report_dir in empty_reports:
            try:
                report_dir.rmdir()
                print(f"  ✅ 已删除: {report_dir.name}")
            except Exception as e:
                print(f"  ❌ 删除失败 {report_dir.name}: {e}")

def cleanup_old_reports(keep_days=7, dry_run=True):
    """清理旧报告（保留最近N天）"""
    reports = get_report_dirs()
    cutoff_date = datetime.now() - timedelta(days=keep_days)
    old_reports = []
    
    for report_dir in reports:
        mtime = datetime.fromtimestamp(report_dir.stat().st_mtime)
        if mtime < cutoff_date:
            old_reports.append((report_dir, mtime))
    
    if not old_reports:
        print(f"✅ 没有找到 {keep_days} 天前的旧报告")
        return
    
    print(f"发现 {len(old_reports)} 个 {keep_days} 天前的旧报告:")
    total_size = 0
    for report_dir, mtime in old_reports:
        size = get_dir_size(report_dir)
        total_size += size
        size_mb = size / (1024 * 1024)
        print(f"  - {report_dir.name}")
        print(f"    创建时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    大小: {size_mb:.2f} MB")
        print(f"    文件数: {count_files_in_dir(report_dir)}")
    
    total_mb = total_size / (1024 * 1024)
    print(f"\n总计可释放空间: {total_mb:.2f} MB")
    
    if dry_run:
        print(f"\n💡 使用 --delete-old 参数实际删除这些目录")
    else:
        print("\n🗑️  正在删除旧报告...")
        for report_dir, _ in old_reports:
            try:
                shutil.rmtree(report_dir)
                print(f"  ✅ 已删除: {report_dir.name}")
            except Exception as e:
                print(f"  ❌ 删除失败 {report_dir.name}: {e}")

def list_reports(detailed=False):
    """列出所有报告"""
    reports = get_report_dirs()
    
    if not reports:
        print("❌ 没有找到基准测试报告")
        return
    
    print(f"找到 {len(reports)} 个基准测试报告:\n")
    
    total_size = 0
    for i, report_dir in enumerate(reports, 1):
        mtime = datetime.fromtimestamp(report_dir.stat().st_mtime)
        file_count = count_files_in_dir(report_dir)
        size = get_dir_size(report_dir)
        total_size += size
        size_mb = size / (1024 * 1024)
        
        status = "✅" if file_count > 0 else "⚠️  空"
        
        print(f"{i}. {status} {report_dir.name}")
        if detailed or file_count == 0:
            print(f"   创建时间: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   文件数量: {file_count}")
            print(f"   目录大小: {size_mb:.2f} MB")
        
        if detailed and file_count > 0:
            # 列出文件
            files = [f for f in report_dir.iterdir() if f.is_file()]
            for f in files[:5]:  # 只显示前5个文件
                fsize = f.stat().st_size / 1024  # KB
                print(f"     - {f.name} ({fsize:.1f} KB)")
            if len(files) > 5:
                print(f"     ... 还有 {len(files) - 5} 个文件")
        print()
    
    total_mb = total_size / (1024 * 1024)
    print(f"总占用空间: {total_mb:.2f} MB")

def main():
    """主函数"""
    if len(sys.argv) < 2:
        print("基准测试报告清理工具")
        print("\n用法:")
        print("  python3 cleanup_benchmark_reports.py list          # 列出所有报告")
        print("  python3 cleanup_benchmark_reports.py list -d       # 详细列出所有报告")
        print("  python3 cleanup_benchmark_reports.py clean         # 查看需要清理的空报告（预览）")
        print("  python3 cleanup_benchmark_reports.py clean --delete # 删除空报告")
        print("  python3 cleanup_benchmark_reports.py old           # 查看需要清理的旧报告（预览）")
        print("  python3 cleanup_benchmark_reports.py old --delete   # 删除7天前的旧报告")
        print("  python3 cleanup_benchmark_reports.py old --delete --days=3  # 删除3天前的旧报告")
        return
    
    command = sys.argv[1].lower()
    
    if command == "list":
        detailed = "-d" in sys.argv or "--detailed" in sys.argv
        list_reports(detailed=detailed)
    
    elif command == "clean":
        dry_run = "--delete" not in sys.argv
        cleanup_empty_reports(dry_run=dry_run)
    
    elif command == "old":
        # 解析保留天数
        keep_days = 7
        for arg in sys.argv:
            if arg.startswith("--days="):
                try:
                    keep_days = int(arg.split("=")[1])
                except:
                    pass
        
        dry_run = "--delete" not in sys.argv
        cleanup_old_reports(keep_days=keep_days, dry_run=dry_run)
    
    else:
        print(f"未知命令: {command}")
        print("使用 'python3 cleanup_benchmark_reports.py' 查看帮助")

if __name__ == "__main__":
    main()

