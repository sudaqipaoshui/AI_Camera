#!/usr/bin/env python 
# coding:utf-8
from pathlib import Path

r = 4
d = 800
count = 40
fallback_start_time='2026-02-06 13:15:00',
fallback_end_time='2026-02-06 13:34:40'
log_file_path = 'Log/20260206/app/131612342_2026-02-06_13-33-19.log'

class TestUpdateRtspSettings(object):

    def test_analyze_log(self, e2e_log_analyzer, project_root):
        """统一分析APP和Camera日志 - 使用插件"""
        # 如果指定了日志文件路径，转换为Path对象
        log_file = None
        if log_file_path:
            log_file = project_root / log_file_path if not Path(log_file_path).is_absolute() else Path(log_file_path)
        
        result = e2e_log_analyzer.analyze_all_logs(
            project_root=project_root,
            expected_circles=r,
            distance=d,
            circles=r,
            fallback_start_time=fallback_start_time,
            fallback_end_time=fallback_end_time,
            log_file=log_file
        )
        