#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
X5摄像头SSH监控数据报告生成工具
从现有CSV数据生成监控报告和图表
"""

import os
import sys
import csv
import argparse
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.font_manager import FontProperties
from datetime import datetime
from matplotlib.lines import Line2D
import pandas as pd
import re


def _parse_bpu_somstatus_raw(raw):
    """从 hrut_somstatus 原始字符串解析出 BPU 温度、频率、使用率。与 test_x5_ssh_24h_monitoring 中逻辑一致。"""
    out = {'temp_bpu': None, 'bpu_freq_mhz': None, 'bpu0_ratio': None}
    if not raw or not str(raw).strip():
        return out
    raw = str(raw).replace('\r\n', '\n').replace('\r', '\n').strip()
    m = re.search(r'BPU\s*:\s*([\d.]+)\s*\(C\)', raw, re.I)
    if m:
        out['temp_bpu'] = float(m.group(1))
    m = re.search(r'bpu0\s*:\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', raw, re.I | re.DOTALL)
    if m:
        out['bpu_freq_mhz'] = int(m.group(2))
        out['bpu0_ratio'] = int(m.group(4))
    return out


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

#Mac字体
# plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial Unicode MS', 'DejaVu Sans']
# plt.rcParams['axes.unicode_minus'] = False


## Linux字体
# # 加载Noto Sans CJK SC字体（替换为你的实际路径）
# noto_font = FontProperties(fname="/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")
# # 全局配置：所有文本默认使用该字体
# plt.rcParams['font.family'] = noto_font.get_name()
# plt.rcParams['axes.unicode_minus'] = False  # 修复负号显示

class X5MonitoringReportGenerator:
    def __init__(self, csv_file_path, output_dir=None):
        """
        初始化报告生成器
        
        Args:
            csv_file_path: CSV数据文件路径
            output_dir: 输出目录，如果为None则使用CSV文件所在目录
        """
        self.csv_file_path = csv_file_path
        self.output_dir = output_dir or os.path.dirname(csv_file_path)
        self.data = None
        self.load_data()
    
    def load_data(self):
        """加载CSV数据"""
        try:
            print(f"正在加载数据文件: {self.csv_file_path}")
            try:
                self.data = pd.read_csv(self.csv_file_path)
            except pd.errors.ParserError:
                # 列数不一致时用 Python 引擎并忽略异常行
                self.data = pd.read_csv(self.csv_file_path, on_bad_lines='warn', engine='python')
            print(f"成功加载 {len(self.data)} 条数据记录")
            
            # 转换时间戳列
            if 'timestamp' in self.data.columns:
                self.data['timestamp'] = pd.to_datetime(self.data['timestamp'])
            
            # 若有 bpu_somstatus 原始列：对每行从原始内容解析 BPU 温度/使用率/频率，缺失或为 0 时回填
            if 'bpu_somstatus' in self.data.columns:
                for col in ('bpu_temperature', 'bpu_usage', 'bpu_cur_freq_mhz'):
                    if col not in self.data.columns:
                        self.data[col] = np.nan
                for idx, raw in self.data['bpu_somstatus'].items():
                    if not raw or not str(raw).strip():
                        continue
                    parsed = _parse_bpu_somstatus_raw(raw)
                    if parsed.get('temp_bpu') is not None:
                        cur = self.data.at[idx, 'bpu_temperature']
                        if pd.isna(cur) or cur == 0:
                            self.data.at[idx, 'bpu_temperature'] = parsed['temp_bpu']
                    if parsed.get('bpu0_ratio') is not None:
                        cur = self.data.at[idx, 'bpu_usage']
                        if pd.isna(cur) or cur == 0:
                            self.data.at[idx, 'bpu_usage'] = parsed['bpu0_ratio']
                    if parsed.get('bpu_freq_mhz') is not None:
                        cur = self.data.at[idx, 'bpu_cur_freq_mhz']
                        if pd.isna(cur) or cur == 0:
                            self.data.at[idx, 'bpu_cur_freq_mhz'] = parsed['bpu_freq_mhz']
            
            # 显示数据基本信息
            print(f"数据时间范围: {self.data['timestamp'].min()} 到 {self.data['timestamp'].max()}")
            print(f"数据列: {list(self.data.columns)}")
            
        except Exception as e:
            print(f"加载数据失败: {e}")
            sys.exit(1)
    
    def generate_charts(self):
        """生成监控图表"""
        if self.data is None or len(self.data) == 0:
            print("没有数据可生成图表")
            return
        
        try:
            print("正在生成监控图表...")
            
            # 确保输出目录存在
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 准备数据
            timestamps = self.data['timestamp']
            temp_data = self.data.get('temperature', [])
            cpu_data = self.data.get('cpu_usage', [])
            memory_data = self.data.get('memory_usage', [])
            disk_data = self.data.get('disk_usage', [])
            load_data = self.data.get('load_avg_1min', [])
            estimated_fps_data = self.data.get('estimated_fps', [])  # analysis fps
            real_fps_data = self.data.get('real_fps', [])  # Actual FPS
            target_fps_data = self.data.get('target_fps', [])  # Target FPS
            smart_fps_data = self.data.get('smart_fps', [])  # Smart fps
            bitrate_data = self.data.get('estimated_bitrate', [])
            latency_data = self.data.get('estimated_latency', [])
            quality_data = self.data.get('video_quality_score', [])
            camera_processes_data = self.data.get('camera_processes_count', [])
            x5_processes_data = self.data.get('x5_processes_count', [])
            encoder_processes_data = self.data.get('encoder_processes_count', [])
            ffmpeg_processes_data = self.data.get('ffmpeg_processes_count', [])
            
            # 新增：从日志中提取的具体数值字段
            camera_logs_fps_data = self.data.get('camera_logs_fps', [])
            camera_errors_data = self.data.get('camera_errors_count', [])
            resolution_logs_data = self.data.get('resolution_logs_value', [])
            video_logs_fps_data = self.data.get('video_logs_fps', [])
            gop_logs_data = self.data.get('gop_logs_value', [])
            keyframe_logs_data = self.data.get('keyframe_logs_value', [])
            
            # BPU 数据（hrut_somstatus），缺列时用 0 填充
            def _col(name, default=0):
                if name in self.data.columns:
                    return self.data[name].fillna(default)
                return pd.Series([default] * len(self.data), index=self.data.index)
            bpu_usage_data = _col('bpu_usage', 0)
            bpu_freq_mhz_data = _col('bpu_cur_freq_mhz', 0)
            bpu_temperature_data = _col('bpu_temperature', 0)
            
            # 创建图表 - 5x2 布局，BPU 合并到 CPU 子图
            fig, ((ax1, ax2), (ax3, ax4), (ax5, ax6), (ax7, ax8), (ax9, ax10)) = plt.subplots(5, 2, figsize=(15, 25))
            fig.suptitle('X5摄像头SSH底层数据监控图表', fontsize=16)
            
            # 温度图表：系统温度 + BPU温度
            if len(temp_data) > 0:
                ax1.plot(timestamps, temp_data, 'r-', linewidth=2, label='系统温度')
                if 'bpu_temperature' in self.data.columns and (bpu_temperature_data > 0).any():
                    ax1.plot(timestamps, bpu_temperature_data, 'm-', linewidth=2, label='BPU温度')
                ax1.axhline(y=80, color='r', linestyle='--', label='阈值(80°C)')
                ax1.set_title('温度监控 (系统 + BPU)')
                ax1.set_ylabel('温度 (°C)')
                ax1.legend()
                ax1.grid(True, alpha=0.3)

            # CPU / BPU 合并：左轴 使用率(%)，右轴 BPU频率(MHz)
            if len(cpu_data) > 0:
                ax2.plot(timestamps, cpu_data, 'b-', linewidth=2, label='CPU使用率')
                ax2.plot(timestamps, bpu_usage_data, 'm-', linewidth=2, label='BPU使用率(ratio)')
                ax2.axhline(y=95, color='r', linestyle='--', label='阈值(95%)')
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
            if len(memory_data) > 0:
                # 绘制内存使用率曲线和阈值线
                line1 = ax3.plot(timestamps, memory_data, 'g-', linewidth=2, label='内存使用率', alpha=0.8)
                line2 = ax3.axhline(y=90, color='r', linestyle='--', alpha=0.7, label='警告阈值(90%)')
                line3 = ax3.axhline(y=80, color='orange', linestyle=':', alpha=0.5, label='高使用率(80%)')
                line4 = ax3.axhline(y=95, color='red', linestyle=':', alpha=0.5, label='危险阈值(95%)')
                
                ax3.set_title('内存使用率监控')
                ax3.set_ylabel('使用率 (%)')
                
                # 计算统计信息和预警信息
                max_memory = max(memory_data)
                avg_memory = sum(memory_data) / len(memory_data)
                min_memory = min(memory_data)
                
                warnings = []
                if max_memory > 80:
                    warnings.append('⚠️ 内存使用率较高')
                if max_memory > 95:
                    warnings.append('🚨 内存使用率危险')
                
                # 组合统计信息文本（使用换行符分隔）
                stats_text = f'最高: {max_memory:.1f}%\n平均: {avg_memory:.1f}%\n最低: {min_memory:.1f}%'
                if warnings:
                    stats_text += '\n\n' + '\n'.join(warnings)
                
                # 创建虚拟线条用于承载统计信息（不显示在图中）
                stats_line = Line2D([], [], color='none', label=stats_text)  # 虚拟线条无实际显示
                
                # 整合所有图例元素（原有线条 + 统计信息虚拟线条）
                lines = line1 + [line2, line3, line4, stats_line]
                labels = [l.get_label() for l in lines]
                
                # 优化图例显示（包含统计信息）
                ax3.legend(lines, labels, 
                        loc='lower right', 
                        fontsize=7, 
                        ncol=2,  # 2列显示（可根据内容调整）
                        framealpha=0.5, 
                        facecolor='white', 
                        edgecolor='black', 
                        fancybox=True, 
                        shadow=False)
                
                ax3.grid(True, alpha=0.3)

            # 改进：磁盘分区监控图表 - 详细分析和预警
            # 检查是否有磁盘分区数据
            disk_root_data = self.data.get('disk_usage_root', [])
            disk_userdata_data = self.data.get('disk_usage_userdata', [])
            disk_app_data = self.data.get('disk_usage_app', [])

            if len(disk_data) > 0:
                # 创建双y轴图表
                ax4_twin = ax4.twinx()
                
                # 左y轴：使用率百分比
                lines = []  # 存储所有需要在图例中显示的线条
                
                # 如果有分区数据，显示多个分区
                if len(disk_root_data) > 0 or len(disk_userdata_data) > 0 or len(disk_app_data) > 0:
                    if len(disk_userdata_data) > 0:
                        line1 = ax4.plot(timestamps, disk_userdata_data, 'g-', linewidth=2, label='userdata分区(/userdata)', alpha=0.8)
                        lines.extend(line1)
                    if len(disk_root_data) > 0:
                        line2 = ax4.plot(timestamps, disk_root_data, 'r-', linewidth=2, label='根分区(/)', alpha=0.8)
                        lines.extend(line2)
                    if len(disk_app_data) > 0:
                        line3 = ax4.plot(timestamps, disk_app_data, 'b-', linewidth=2, label='app分区(/app)', alpha=0.8)
                        lines.extend(line3)
                    
                    ax4.set_title('磁盘分区监控（多分区详细分析）')
                else:
                    # 没有分区数据，显示总体磁盘使用率
                    if all(usage == 100.0 for usage in disk_data):
                        line1 = ax4.plot(timestamps, disk_data, 'r-', linewidth=2, label='根分区使用率(/)', alpha=0.8)
                        lines.extend(line1)
                        ax4.set_title('磁盘使用率监控（根分区 - 使用率100%）')
                    else:
                        line1 = ax4.plot(timestamps, disk_data, 'm-', linewidth=2, label='磁盘使用率', alpha=0.8)
                        lines.extend(line1)
                        ax4.set_title('磁盘使用率监控（详细分析）')
                
                # 添加阈值线
                ax4.axhline(y=90, color='m', linestyle='--', alpha=0.7, label='警告阈值(90%)')
                ax4.axhline(y=95, color='red', linestyle=':', alpha=0.5, label='危险阈值(95%)')
                # 将阈值线加入图例列表（axhline返回的是Line2D对象，直接添加）
                lines.append(ax4.lines[-2])  # 警告阈值线（倒数第二条线）
                lines.append(ax4.lines[-1])  # 危险阈值线（最后一条线）
                
                # 右y轴：使用率趋势（变化率）
                trend_data = disk_userdata_data if len(disk_userdata_data) > 0 else disk_data
                if len(trend_data) > 1:
                    usage_trend = []
                    for i in range(1, len(trend_data)):
                        trend = trend_data[i] - trend_data[i-1]
                        usage_trend.append(trend)
                    
                    trend_timestamps = timestamps[1:] if len(timestamps) > 1 else timestamps
                    if usage_trend:
                        line_trend = ax4_twin.plot(trend_timestamps, usage_trend, 'purple', linewidth=1, 
                                                label='使用率变化趋势', linestyle=':', alpha=0.6)
                        lines.extend(line_trend)
                
                # 设置标签和标题
                ax4.set_ylabel('使用率 (%)', color='black')
                ax4_twin.set_ylabel('使用率变化 (%)', color='purple')
                
                # --------------------------
                # 生成统计信息并转为图例项
                # --------------------------
                import matplotlib.lines as mlines  # 用于创建虚拟线条
                
                # 1. 生成统计文本（与原逻辑一致，但改为列表形式）
                if len(disk_root_data) > 0 or len(disk_userdata_data) > 0 or len(disk_app_data) > 0:
                    partition_stats = []
                    warnings = []
                    
                    if len(disk_userdata_data) > 0:
                        max_userdata = max(disk_userdata_data)
                        avg_userdata = sum(disk_userdata_data) / len(disk_userdata_data)
                        partition_stats.append(f'userdata: 最高{max_userdata:.1f}%, 平均{avg_userdata:.1f}%')
                        if max_userdata > 90:
                            warnings.append('⚠️ userdata分区使用率过高')
                    
                    if len(disk_root_data) > 0:
                        max_root = max(disk_root_data)
                        avg_root = sum(disk_root_data) / len(disk_root_data)
                        partition_stats.append(f'根分区: 最高{max_root:.1f}%, 平均{avg_root:.1f}%')
                        if max_root > 90:
                            warnings.append('⚠️ 根分区使用率过高')
                    
                    if len(disk_app_data) > 0:
                        max_app = max(disk_app_data)
                        avg_app = sum(disk_app_data) / len(disk_app_data)
                        partition_stats.append(f'app分区: 最高{max_app:.1f}%, 平均{avg_app:.1f}%')
                        if max_app > 90:
                            warnings.append('⚠️ app分区使用率过高')
                    
                    stats_list = partition_stats
                    if warnings:
                        stats_list.extend(warnings)
                else:
                    max_disk = max(disk_data)
                    avg_disk = sum(disk_data) / len(disk_data)
                    
                    warnings = []
                    if max_disk > 90:
                        warnings.append('⚠️ 磁盘使用率过高')
                    if max_disk > 95:
                        warnings.append('🚨 磁盘使用率危险')
                    
                    if all(usage == 100.0 for usage in disk_data):
                        stats_list = [
                            f'根分区使用率: {max_disk:.1f}%',
                            '注意: 根分区已满',
                            '建议: 检查其他分区'
                        ]
                        stats_list.extend(warnings)
                    else:
                        stats_list = [
                            f'最高使用率: {max_disk:.1f}%',
                            f'平均使用率: {avg_disk:.1f}%'
                        ]
                        stats_list.extend(warnings)
                
                # 2. 添加分隔线（视觉上区分图表线和统计信息）
                lines.append(mlines.Line2D([], [], linestyle='-', color='gray', alpha=0.5, label='----- 统计信息 -----'))
                
                # 3. 创建虚拟线条承载统计文本（线条不可见，仅显示标签）
                for stat in stats_list:
                    # 虚拟线条：无颜色、无线条样式，仅用于图例显示文本
                    virtual_line = mlines.Line2D([], [], color='none', linestyle='', label=stat)
                    lines.append(virtual_line)
                
                # --------------------------
                # 生成合并后的图例
                # --------------------------
                labels = [l.get_label() for l in lines]
                # 调整图例参数：增加列数避免过长，调整位置和大小
                ax4.legend(lines, labels, loc='center right', fontsize=7, 
                        ncol=2,  # 单列显示（可根据内容调整为2列）
                        framealpha=0.5, 
                        facecolor='white', 
                        edgecolor='black', 
                        fancybox=True, 
                        shadow=False)
                
                ax4.grid(True, alpha=0.3)

            # FPS监控图表 - 显示所有FPS字段
            # 检查是否有FPS数据
            has_estimated_fps = len(estimated_fps_data) > 0 and any(fps > 0 for fps in estimated_fps_data)
            has_real_fps = len(real_fps_data) > 0 and any(fps > 0 for fps in real_fps_data)
            has_target_fps = len(target_fps_data) > 0 and any(fps > 0 for fps in target_fps_data)
            has_smart_fps = len(smart_fps_data) > 0 and any(fps > 0 for fps in smart_fps_data)
            
            if has_estimated_fps or has_real_fps or has_target_fps or has_smart_fps:
                # 绘制所有FPS数据线
                if has_real_fps:
                    ax5.plot(timestamps, real_fps_data, 'green', linewidth=2, label='Actual FPS', alpha=0.8)
                if has_target_fps:
                    ax5.plot(timestamps, target_fps_data, 'blue', linewidth=2, label='Target FPS', alpha=0.8)
                if has_smart_fps:
                    ax5.plot(timestamps, smart_fps_data, 'purple', linewidth=2, label='Smart FPS', alpha=0.8)
                if has_estimated_fps:
                    ax5.plot(timestamps, estimated_fps_data, 'orange', linewidth=2, label='Analysis FPS', alpha=0.8)
                
                # 添加阈值参考线（可选）
                ax5.axhline(y=25, color='orange', linestyle='--', alpha=0.5, label='参考线(25)')
                ax5.axhline(y=20, color='red', linestyle='--', alpha=0.5, label='参考线(20)')
                ax5.axhline(y=30, color='blue', linestyle=':', alpha=0.3, label='参考线(30)')
                
                ax5.set_title('FPS监控')
                ax5.set_ylabel('FPS')
                ax5.legend()
                ax5.grid(True, alpha=0.3)
                
                # 设置y轴范围
                all_fps = []
                if has_estimated_fps:
                    all_fps.extend([fps for fps in estimated_fps_data if fps > 0])
                if has_real_fps:
                    all_fps.extend([fps for fps in real_fps_data if fps > 0])
                if has_target_fps:
                    all_fps.extend([fps for fps in target_fps_data if fps > 0])
                if has_smart_fps:
                    all_fps.extend([fps for fps in smart_fps_data if fps > 0])
                
                if all_fps:
                    min_fps = min(all_fps)
                    max_fps = max(all_fps)
                    ax5.set_ylim(max(0, min_fps - 2), min(35, max_fps + 2))
            else:
                # 没有FPS数据时显示提示
                ax5.text(0.5, 0.5, 'FPS数据不可用', ha='center', va='center', 
                        transform=ax5.transAxes, fontsize=12, color='red')
                ax5.set_title('FPS监控（无数据）')
                ax5.set_ylabel('FPS')

            # 摄像头进程监控图表
            if len(camera_processes_data) > 0:
                ax6.plot(timestamps, camera_processes_data, 'purple', linewidth=2, label='摄像头进程数')
                if len(x5_processes_data) > 0:
                    ax6.plot(timestamps, x5_processes_data, 'brown', linewidth=2, label='X5进程数')
                if len(encoder_processes_data) > 0:
                    ax6.plot(timestamps, encoder_processes_data, 'gray', linewidth=2, label='编码器进程数')
                if len(ffmpeg_processes_data) > 0:
                    ax6.plot(timestamps, ffmpeg_processes_data, 'pink', linewidth=2, label='FFmpeg进程数')
                ax6.set_title('摄像头进程监控')
                ax6.set_ylabel('进程数量')
                ax6.legend()
                ax6.grid(True, alpha=0.3)

            # 码率监控图表
            if len(bitrate_data) > 0:
                ax7.plot(timestamps, bitrate_data, 'cyan', linewidth=2, label='估算码率')
                ax7.axhline(y=2000, color='cyan', linestyle='--', label='目标码率(2Mbps)')
                ax7.set_title('码率监控')
                ax7.set_ylabel('码率 (kbps)')
                ax7.legend()
                ax7.grid(True, alpha=0.3)

            # 延迟监控图表
            if len(latency_data) > 0:
                ax8.plot(timestamps, latency_data, 'orange', linewidth=2, label='网络延迟')
                ax8.axhline(y=10, color='orange', linestyle='--', label='延迟阈值(10ms)')
                ax8.set_title('延迟监控')
                ax8.set_ylabel('延迟 (ms)')
                ax8.legend()
                ax8.grid(True, alpha=0.3)

            # 改进：错误日志监控图表 - 详细分析和趋势
            if len(camera_logs_fps_data) > 0 or len(camera_errors_data) > 0:
                # 计算错误率趋势（使用camera_logs_fps作为总日志数的代理）
                error_rates = []
                for i, (logs, errors) in enumerate(zip(camera_logs_fps_data, camera_errors_data)):
                    if logs > 0:
                        error_rate = (errors / logs) * 100
                    else:
                        error_rate = 0
                    error_rates.append(error_rate)
                
                # 创建双y轴图表
                ax9_twin = ax9.twinx()
                
                # 左y轴：日志数量
                lines = []
                if len(camera_logs_fps_data) > 0:
                    line1 = ax9.plot(timestamps, camera_logs_fps_data, 'blue', linewidth=2, label='摄像头日志总数', alpha=0.7)
                    lines.extend(line1)
                if len(camera_errors_data) > 0:
                    line2 = ax9.plot(timestamps, camera_errors_data, 'red', linewidth=2, label='摄像头错误日志', alpha=0.7)
                    lines.extend(line2)
                
                # 右y轴：错误率
                if error_rates:
                    line3 = ax9_twin.plot(timestamps, error_rates, 'orange', linewidth=2, label='错误率(%)', linestyle='--')
                    lines.extend(line3)
                
                # 添加错误率阈值线并纳入图例
                line4 = ax9_twin.axhline(y=10, color='orange', linestyle=':', alpha=0.5, label='错误率阈值(10%)')
                line5 = ax9_twin.axhline(y=20, color='red', linestyle=':', alpha=0.5, label='错误率警告(20%)')
                lines.extend([line4, line5])
                
                # 处理统计信息并添加到图例
                if len(camera_errors_data) > 0:
                    max_errors = max(camera_errors_data)
                    avg_errors = sum(camera_errors_data) / len(camera_errors_data)
                    max_error_rate = max(error_rates) if error_rates else 0
                    
                    # 统计信息标签
                    stats_labels = [
                        f'最大错误数: {max_errors}',
                        f'平均错误数: {avg_errors:.1f}',
                        f'最大错误率: {max_error_rate:.1f}%'
                    ]
                    
                    # 创建不可见线条承载统计信息
                    for label in stats_labels:
                        stats_line = Line2D([], [], linestyle='none', label=label)
                        lines.append(stats_line)
                
                # 设置标签和标题
                ax9.set_title('摄像头错误日志监控（含错误率分析）')
                ax9.set_ylabel('日志条目数', color='blue')
                ax9_twin.set_ylabel('错误率 (%)', color='orange')
                
                # 合并所有图例（包含线条标签和统计信息）
                labels = [l.get_label() for l in lines]
                ax9.legend(lines, labels, loc='center right', fontsize=7, 
                        ncol=2,  # 单列显示（可根据内容调整为2列）
                        framealpha=0.5, 
                        facecolor='white', 
                        edgecolor='black', 
                        fancybox=True, 
                        shadow=False)
                
                ax9.grid(True, alpha=0.3)

            # 改进：视频性能监控图表 - 优化分辨率坐标显示
            # 修复：使用real_resolution字段而不是resolution_logs_value
            real_resolution_data = self.data.get('real_resolution', [])
                    
            if len(real_resolution_data) > 0 or len(video_logs_fps_data) > 0 or len(gop_logs_data) > 0:
                # 创建双y轴图表
                ax10_twin = ax10.twinx()
                
                # 左y轴：分辨率（转换为分辨率等级）
                resolution_levels = []
                resolution_labels = []
                
                for res in real_resolution_data:
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
                lines = []
                if resolution_levels:
                    line1 = ax10.plot(timestamps, resolution_levels, 'green', linewidth=2, label='分辨率等级', marker='o', markersize=4)
                    lines.extend(line1)
                # 使用所有FPS字段数据
                if len(real_fps_data) > 0 and any(fps > 0 for fps in real_fps_data):
                    line2 = ax10_twin.plot(timestamps, real_fps_data, 'purple', linewidth=2, label='Actual FPS', marker='s', markersize=3)
                    lines.extend(line2)
                if len(target_fps_data) > 0 and any(fps > 0 for fps in target_fps_data):
                    line_target = ax10_twin.plot(timestamps, target_fps_data, 'blue', linewidth=2, label='Target FPS', marker='^', markersize=3)
                    lines.extend(line_target)
                if len(smart_fps_data) > 0 and any(fps > 0 for fps in smart_fps_data):
                    line_smart = ax10_twin.plot(timestamps, smart_fps_data, 'cyan', linewidth=2, label='Smart FPS', marker='d', markersize=3)
                    lines.extend(line_smart)
                if len(estimated_fps_data) > 0 and any(fps > 0 for fps in estimated_fps_data):
                    line_analysis = ax10_twin.plot(timestamps, estimated_fps_data, 'orange', linewidth=2, label='analysis FPS', marker='s', markersize=3)
                    lines.extend(line_analysis)
                if len(gop_logs_data) > 0:
                    line3 = ax10_twin.plot(timestamps, gop_logs_data, 'orange', linewidth=2, label='GOP值', marker='^', markersize=3)
                    lines.extend(line3)
                
                # 设置分辨率y轴标签和刻度
                ax10.set_ylabel('分辨率等级', color='green')
                ax10.set_yticks([0, 1, 2, 3, 4])
                ax10.set_yticklabels(['无数据', '其他', '720p', '2K', '4K'])
                ax10.set_ylim(-0.5, 4.5)
                
                # 添加分辨率参考线
                ref_line1 = ax10.axhline(y=2, color='gray', linestyle=':', alpha=0.5, label='720p参考线')
                ref_line2 = ax10.axhline(y=3, color='blue', linestyle=':', alpha=0.5, label='2K参考线')
                ref_line3 = ax10.axhline(y=4, color='red', linestyle=':', alpha=0.5, label='4K参考线')
                lines.extend([ref_line1, ref_line2, ref_line3])  # 将参考线加入线条列表
                
                # 添加FPS参考线
                ref_line4 = ax10_twin.axhline(y=30, color='purple', linestyle=':', alpha=0.5, label='30fps参考线')
                ref_line5 = ax10_twin.axhline(y=60, color='purple', linestyle=':', alpha=0.5, label='60fps参考线')
                lines.extend([ref_line4, ref_line5])  # 将FPS参考线加入线条列表
                
                # 生成统计信息并添加到图例
                stats_text = ""
                if resolution_levels:
                    max_level = max(resolution_levels)
                    avg_level = sum(resolution_levels) / len(resolution_levels)
                    # 修复：使用real_fps数据计算统计信息
                    if len(real_fps_data) > 0 and any(fps > 0 for fps in real_fps_data):
                        valid_fps = [fps for fps in real_fps_data if fps > 0]
                        max_fps = max(valid_fps)
                        avg_fps = sum(valid_fps) / len(valid_fps)
                    elif len(estimated_fps_data) > 0 and any(fps > 0 for fps in estimated_fps_data):
                        valid_fps = [fps for fps in estimated_fps_data if fps > 0]
                        max_fps = max(valid_fps)
                        avg_fps = sum(valid_fps) / len(valid_fps)
                    else:
                        max_fps = 0
                        avg_fps = 0
                    
                    # 确定分辨率等级名称
                    level_names = {0: "无数据", 1: "其他", 2: "720p", 3: "2K", 4: "4K"}
                    max_res_name = level_names.get(max_level, "未知")
                    avg_res_name = level_names.get(round(avg_level), "未知")
                    
                    # 构建统计信息文本（使用换行符分隔）
                    stats_text = f'统计信息:\n最高分辨率: {max_res_name}\n平均分辨率: {avg_res_name}\n最高FPS: {max_fps:.1f}\n平均FPS: {avg_fps:.1f}'
                    
                    # 创建虚拟线条（不可见）用于在图例中显示统计信息
                    stats_line = Line2D([], [], color='none', label=stats_text)
                    lines.append(stats_line)
                
                # 设置标签和标题
                ax10.set_title('视频性能监控（分辨率、FPS、GOP）')
                ax10_twin.set_ylabel('FPS / GOP值', color='purple')
                
                # 合并所有元素为一个图例
                labels = [l.get_label() for l in lines]
                ax10.legend(lines, labels, loc='center right', fontsize=7, 
                        ncol=2,  # 单列显示（可根据内容调整为2列）
                        framealpha=0.5, 
                        facecolor='white', 
                        edgecolor='black', 
                        fancybox=True, 
                        shadow=False)
                
                ax10.grid(True, alpha=0.3)

            # 智能设置x轴格式 - 限制刻度数量避免 "exceeds Locator.MAXTICKS (1000)"
            if len(timestamps) > 0:
                try:
                    if hasattr(timestamps, 'iloc'):
                        time_span = timestamps.iloc[-1] - timestamps.iloc[0]
                    else:
                        time_span = timestamps[-1] - timestamps[0]
                    total_hours = time_span.total_seconds() / 3600
                except Exception as e:
                    print(f"时间计算错误: {e}")
                    total_hours = 2
                # 使用 AutoDateLocator(maxticks=25) 限制刻度数量，避免数据量大时超过 MAXTICKS
                locator = mdates.AutoDateLocator(maxticks=25)
                if total_hours <= 24:
                    time_format = '%H:%M'
                else:
                    time_format = '%m-%d %H:%M'
                all_axes = [ax1, ax2, ax3, ax4, ax5, ax6, ax7, ax8, ax9, ax10]
                for ax in all_axes:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter(time_format))
                    ax.xaxis.set_major_locator(locator)
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
                print(f"监控时长: {total_hours:.1f}小时，x轴刻度已限制为最多25个")
            else:
                all_axes = [ax1, ax2, ax3, ax4, ax5, ax6, ax7, ax8, ax9, ax10]
                locator = mdates.AutoDateLocator(maxticks=25)
                for ax in all_axes:
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                    ax.xaxis.set_major_locator(locator)
                    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

            plt.tight_layout()
            
            # 保存图表
            chart_file = os.path.join(self.output_dir, 'ssh_monitoring_charts.png')
            plt.savefig(chart_file, dpi=300, bbox_inches='tight')
            plt.close()
            
            print(f"图表已保存到: {chart_file}")
            
        except Exception as e:
            print(f"生成图表失败: {e}")
            import traceback
            traceback.print_exc()
    
    def generate_statistics_report(self):
        """生成统计报告"""
        if self.data is None or len(self.data) == 0:
            print("没有数据可生成统计报告")
            return
        
        try:
            print("正在生成统计报告...")
            
            # 确保输出目录存在
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 计算统计信息
            total_records = len(self.data)
            successful_records = len(self.data[self.data.get('success', True) == True])
            success_rate = (successful_records / total_records) * 100 if total_records > 0 else 0
            
            # 计算平均值（处理空数据）
            def safe_mean(data, default=0):
                if len(data) > 0 and not data.isna().all():
                    return data.dropna().mean()
                return default
            
            def safe_max(data, default=0):
                if len(data) > 0 and not data.isna().all():
                    return data.dropna().max()
                return default
            
            def safe_min(data, default=0):
                if len(data) > 0 and not data.isna().all():
                    return data.dropna().min()
                return default
            
            # 计算各项指标
            avg_temp = safe_mean(self.data.get('temperature', []))
            max_temp = safe_max(self.data.get('temperature', []))
            min_temp = safe_min(self.data.get('temperature', []))
            
            avg_cpu = safe_mean(self.data.get('cpu_usage', []))
            max_cpu = safe_max(self.data.get('cpu_usage', []))
            min_cpu = safe_min(self.data.get('cpu_usage', []))
            
            avg_memory = safe_mean(self.data.get('memory_usage', []))
            max_memory = safe_max(self.data.get('memory_usage', []))
            min_memory = safe_min(self.data.get('memory_usage', []))
            
            avg_disk = safe_mean(self.data.get('disk_usage', []))
            max_disk = safe_max(self.data.get('disk_usage', []))
            min_disk = safe_min(self.data.get('disk_usage', []))
            
            avg_load = safe_mean(self.data.get('load_avg_1min', []))
            max_load = safe_max(self.data.get('load_avg_1min', []))
            min_load = safe_min(self.data.get('load_avg_1min', []))
            
            avg_fps = safe_mean(self.data.get('estimated_fps', []))
            max_fps = safe_max(self.data.get('estimated_fps', []))
            min_fps = safe_min(self.data.get('estimated_fps', []))
            
            avg_bitrate = safe_mean(self.data.get('estimated_bitrate', []))
            max_bitrate = safe_max(self.data.get('estimated_bitrate', []))
            min_bitrate = safe_min(self.data.get('estimated_bitrate', []))
            
            avg_latency = safe_mean(self.data.get('estimated_latency', []))
            max_latency = safe_max(self.data.get('estimated_latency', []))
            min_latency = safe_min(self.data.get('estimated_latency', []))
            
            avg_quality = safe_mean(self.data.get('video_quality_score', []))
            max_quality = safe_max(self.data.get('video_quality_score', []))
            min_quality = safe_min(self.data.get('video_quality_score', []))
            
            # 进程统计
            avg_camera_processes = safe_mean(self.data.get('camera_processes_count', []))
            max_camera_processes = safe_max(self.data.get('camera_processes_count', []))
            min_camera_processes = safe_min(self.data.get('camera_processes_count', []))
            
            avg_x5_processes = safe_mean(self.data.get('x5_processes_count', []))
            max_x5_processes = safe_max(self.data.get('x5_processes_count', []))
            min_x5_processes = safe_min(self.data.get('x5_processes_count', []))
            
            # BPU 统计（列可能不存在，用 0 填充后计算）
            def _bpu_col(name):
                if name in self.data.columns:
                    return self.data[name].fillna(0)
                return pd.Series([0] * len(self.data), index=self.data.index)
            bpu_temp_series = _bpu_col('bpu_temperature')
            bpu_usage_series = _bpu_col('bpu_usage')
            avg_bpu_temp = safe_mean(bpu_temp_series)
            max_bpu_temp = safe_max(bpu_temp_series)
            min_bpu_temp = safe_min(bpu_temp_series)
            avg_bpu_usage = safe_mean(bpu_usage_series)
            max_bpu_usage = safe_max(bpu_usage_series)
            min_bpu_usage = safe_min(bpu_usage_series)
            
            # 生成报告
            report = f"""
===== X5摄像头SSH底层数据统计报告 =====

数据文件: {self.csv_file_path}
数据时间范围: {self.data['timestamp'].min()} - {self.data['timestamp'].max()}
总记录数: {total_records}
成功记录: {successful_records}
成功率: {success_rate:.2f}%

硬件统计:
温度:
- 平均值: {avg_temp:.2f}°C
- 最大值: {max_temp:.2f}°C
- 最小值: {min_temp:.2f}°C
- 阈值: 80°C

CPU使用率:
- 平均值: {avg_cpu:.2f}%
- 最大值: {max_cpu:.2f}%
- 最小值: {min_cpu:.2f}%
- 阈值: 95%

BPU (hrut_somstatus):
- BPU温度 平均: {avg_bpu_temp:.2f}°C, 最大: {max_bpu_temp:.2f}°C, 最小: {min_bpu_temp:.2f}°C
- BPU使用率(ratio) 平均: {avg_bpu_usage:.2f}, 最大: {max_bpu_usage:.2f}, 最小: {min_bpu_usage:.2f}

内存使用率:
- 平均值: {avg_memory:.2f}%
- 最大值: {max_memory:.2f}%
- 最小值: {min_memory:.2f}%
- 阈值: 90%

磁盘使用率:
- 平均值: {avg_disk:.2f}%
- 最大值: {max_disk:.2f}%
- 最小值: {min_disk:.2f}%
- 阈值: 90%

系统负载:
- 平均值: {avg_load:.2f}
- 最大值: {max_load:.2f}
- 最小值: {min_load:.2f}

视频性能统计:
FPS:
- 平均值: {avg_fps:.2f}
- 最大值: {max_fps:.2f}
- 最小值: {min_fps:.2f}

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

异常检测:
"""
            
            # 添加异常检测
            if max_temp > 80:
                report += f"- ⚠️ 温度超过阈值: 最高 {max_temp:.2f}°C\n"
            if max_cpu > 95:
                report += f"- ⚠️ CPU使用率超过阈值: 最高 {max_cpu:.2f}%\n"
            if max_memory > 90:
                report += f"- ⚠️ 内存使用率超过阈值: 最高 {max_memory:.2f}%\n"
            if max_disk > 90:
                report += f"- ⚠️ 磁盘使用率超过阈值: 最高 {max_disk:.2f}%\n"
            if min_fps < 20 and avg_fps > 0:
                report += f"- ⚠️ FPS低于阈值: 最低 {min_fps:.2f}\n"
            if max_latency > 10 and avg_latency > 0:
                report += f"- ⚠️ 延迟超过阈值: 最高 {max_latency:.2f}ms\n"
            
            # 保存报告
            report_file = os.path.join(self.output_dir, 'monitoring_statistics_report.txt')
            with open(report_file, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"统计报告已保存到: {report_file}")
            print("\n" + "="*50)
            print(report)
            print("="*50)
            
        except Exception as e:
            print(f"生成统计报告失败: {e}")
            import traceback
            traceback.print_exc()
    
    def generate_summary_report(self):
        """生成汇总报告"""
        if self.data is None or len(self.data) == 0:
            print("没有数据可生成汇总报告")
            return
        
        try:
            print("正在生成汇总报告...")
            
            # 确保输出目录存在
            os.makedirs(self.output_dir, exist_ok=True)
            
            # 计算关键指标
            total_records = len(self.data)
            successful_records = len(self.data[self.data.get('success', True) == True])
            success_rate = (successful_records / total_records) * 100 if total_records > 0 else 0
            
            # 计算监控时长
            if 'timestamp' in self.data.columns and len(self.data) > 1:
                start_time = self.data['timestamp'].min()
                end_time = self.data['timestamp'].max()
                duration = (end_time - start_time).total_seconds()
                duration_hours = duration / 3600
            else:
                duration_hours = 0
            
            # 判断监控状态
            max_temp = self.data.get('temperature', []).max() if len(self.data) > 0 else 0
            max_cpu = self.data.get('cpu_usage', []).max() if len(self.data) > 0 else 0
            max_memory = self.data.get('memory_usage', []).max() if len(self.data) > 0 else 0
            min_fps = self.data.get('estimated_fps', []).min() if len(self.data) > 0 else 0
            
            # 生成汇总
            summary = f"""
===== X5摄像头SSH监控汇总报告 =====

📊 监控概览:
- 监控时长: {duration_hours:.1f}小时
- 数据记录: {total_records}条
- 成功率: {success_rate:.2f}%

📈 关键指标:
- 最高温度: {max_temp:.1f}°C {'✅' if max_temp <= 80 else '⚠️'}
- 最高CPU: {max_cpu:.1f}% {'✅' if max_cpu <= 95 else '⚠️'}
- 最高内存: {max_memory:.1f}% {'✅' if max_memory <= 90 else '⚠️'}
- 最低FPS: {min_fps:.1f} {'✅' if min_fps >= 20 else '⚠️'}

🎯 监控状态: {'✅ 正常' if success_rate >= 95 and max_temp <= 80 and max_cpu <= 95 and max_memory <= 90 and min_fps >= 20 else '⚠️ 异常'}

📁 报告文件:
- 数据文件: {os.path.basename(self.csv_file_path)}
- 图表文件: ssh_monitoring_charts.png
- 统计报告: monitoring_statistics_report.txt
"""
            
            # 保存汇总报告
            summary_file = os.path.join(self.output_dir, 'monitoring_summary_report.txt')
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary)
            
            print(f"汇总报告已保存到: {summary_file}")
            print(summary)
            
        except Exception as e:
            print(f"生成汇总报告失败: {e}")
            import traceback
            traceback.print_exc()
    
    def generate_all_reports(self):
        """生成所有报告"""
        print("开始生成X5摄像头监控报告...")
        print(f"数据文件: {self.csv_file_path}")
        print(f"输出目录: {self.output_dir}")
        print("-" * 50)
        
        # 生成图表
        self.generate_charts()
        
        # 生成统计报告
        self.generate_statistics_report()
        
        # 生成汇总报告
        self.generate_summary_report()
        
        print("-" * 50)
        print("✅ 所有报告生成完成！")
        print(f"📁 输出目录: {self.output_dir}")

def main():
    parser = argparse.ArgumentParser(description='X5摄像头SSH监控数据报告生成工具')
    parser.add_argument('csv_file', help='CSV数据文件路径')
    parser.add_argument('-o', '--output', help='输出目录（可选，默认为CSV文件所在目录）')
    parser.add_argument('--charts-only', action='store_true', help='仅生成图表')
    parser.add_argument('--stats-only', action='store_true', help='仅生成统计报告')
    parser.add_argument('--summary-only', action='store_true', help='仅生成汇总报告')
    
    args = parser.parse_args()
    
    # 检查CSV文件是否存在
    if not os.path.exists(args.csv_file):
        print(f"错误: CSV文件不存在: {args.csv_file}")
        sys.exit(1)
    
    # 创建报告生成器
    generator = X5MonitoringReportGenerator(args.csv_file, args.output)
    
    # 根据参数生成相应的报告
    if args.charts_only:
        generator.generate_charts()
    elif args.stats_only:
        generator.generate_statistics_report()
    elif args.summary_only:
        generator.generate_summary_report()
    else:
        # 生成所有报告
        generator.generate_all_reports()

if __name__ == '__main__':
    main()

