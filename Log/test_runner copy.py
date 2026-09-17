#!/usr/bin/env python 
# coding:utf-8

r = 5
d = 800
count = 43
fallback_start_time = '2025-12-16 10:20:30'
fallback_end_time = '2025-12-16 10:36:10'

class TestUpdateRtspSettings(object):

    def test_analyze_log(self, e2e_log_analyzer, project_root):
        """统一分析APP和Camera日志 - 使用插件"""
        result = e2e_log_analyzer.analyze_all_logs(
            project_root=project_root,
            expected_circles=r,
            distance=d,
            circles=r,
            fallback_start_time=fallback_start_time,
            fallback_end_time=fallback_end_time
        )
        