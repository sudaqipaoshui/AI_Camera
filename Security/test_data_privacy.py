#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI摄像头数据隐私保护测试

测试内容：
- 敏感数据泄露检测
- 数据加密传输验证
- 个人信息保护测试
- 数据存储安全
- 隐私合规性检查
"""

import allure
import pytest
import requests
import json
import re
import time
import base64
from urllib.parse import urljoin
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@allure.feature('security')
@allure.story('data-privacy')
class TestDataPrivacy:
    """数据隐私保护测试类"""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, env):
        """测试环境初始化"""
        self.env = env
        self.base_url = self.env.get('host', {}).get('camera', 'http://192.168.2.119')
        self.session = requests.Session()
        self.privacy_violations = []
        
        # 敏感数据模式
        self.sensitive_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'(\+?86)?1[3-9]\d{9}|\d{3,4}-\d{7,8}',
            'id_card': r'\d{17}[\dXx]|\d{15}',
            'credit_card': r'\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}',
            'password': r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+["\']?',
            'token': r'token["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+["\']?',
            'api_key': r'api[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+["\']?',
            'secret': r'secret["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+["\']?',
            'ip_address': r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b',
            'mac_address': r'\b([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})\b'
        }

    def _log_privacy_violation(self, test_name, description, severity="HIGH"):
        """记录隐私违规"""
        violation = {
            'test': test_name,
            'description': description,
            'severity': severity,
            'timestamp': time.time()
        }
        self.privacy_violations.append(violation)
        logger.warning(f"隐私违规: {test_name} - {description}")

    @allure.title("测试敏感数据泄露")
    @allure.description("检查API响应中是否泄露敏感信息")
    def test_sensitive_data_leakage(self):
        """测试敏感数据泄露"""
        allure.dynamic.severity(allure.severity_level.CRITICAL)
        
        # 测试接口列表
        test_endpoints = [
            '/api/v1/device/info',
            '/api/v1/user/info',
            '/api/v1/camera/status',
            '/api/v1/settings/config',
            '/api/v1/log/list',
            '/api/v1/face/data',
            '/api/v1/error/logs',
            '/api/v1/debug/info'
        ]
        
        for endpoint in test_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    response_text = response.text
                    
                    # 检查各种敏感数据模式
                    for data_type, pattern in self.sensitive_patterns.items():
                        matches = re.findall(pattern, response_text, re.IGNORECASE)
                        if matches:
                            self._log_privacy_violation(
                                "敏感数据泄露",
                                f"在 {endpoint} 中发现 {data_type} 数据: {matches[:3]}",
                                "CRITICAL"
                            )
                            allure.attach(
                                f"敏感数据泄露\n端点: {endpoint}\n数据类型: {data_type}\n匹配数据: {matches}\n完整响应: {response_text}",
                                name="敏感数据泄露",
                                attachment_type=allure.attachment_type.TEXT
                            )
            
            except Exception as e:
                logger.debug(f"敏感数据泄露测试异常: {e}")

    @allure.title("测试个人信息保护")
    @allure.description("检查个人信息是否正确保护")
    def test_personal_information_protection(self):
        """测试个人信息保护"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 个人信息相关接口
        personal_info_endpoints = [
            '/api/v1/user/profile',
            '/api/v1/user/list',
            '/api/v1/face/features',
            '/api/v1/face/recognition',
            '/api/v1/analytics/users'
        ]
        
        for endpoint in personal_info_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                    
                    # 检查是否返回了完整的个人信息
                    sensitive_fields = ['password', 'secret', 'private_key', 'ssn', 'id_card', 'phone', 'email']
                    
                    for field in sensitive_fields:
                        if field in str(response_data).lower():
                            self._log_privacy_violation(
                                "个人信息泄露",
                                f"在 {endpoint} 中发现敏感字段: {field}",
                                "HIGH"
                            )
            
            except Exception as e:
                logger.debug(f"个人信息保护测试异常: {e}")

    @allure.title("测试数据加密传输")
    @allure.description("验证敏感数据是否加密传输")
    def test_data_encryption_transmission(self):
        """测试数据加密传输"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 检查是否使用HTTPS
        if not self.base_url.startswith('https://'):
            self._log_privacy_violation(
                "数据加密传输",
                "系统使用HTTP协议，数据传输未加密",
                "HIGH"
            )
        
        # 测试敏感数据接口
        sensitive_endpoints = [
            '/api/v1/auth/login',
            '/api/v1/user/register',
            '/api/v1/face/upload',
            '/api/v1/data/upload'
        ]
        
        for endpoint in sensitive_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                
                # 测试POST请求（通常包含敏感数据）
                test_data = {
                    'username': 'test_user',
                    'password': 'test_password',
                    'email': 'test@example.com'
                }
                
                response = self.session.post(url, json=test_data, timeout=10)
                
                # 检查响应头中的安全配置
                security_headers = [
                    'Strict-Transport-Security',
                    'X-Content-Type-Options',
                    'X-Frame-Options'
                ]
                
                missing_headers = []
                for header in security_headers:
                    if header not in response.headers:
                        missing_headers.append(header)
                
                if missing_headers:
                    self._log_privacy_violation(
                        "安全头缺失",
                        f"在 {endpoint} 中缺少安全头: {missing_headers}",
                        "MEDIUM"
                    )
            
            except Exception as e:
                logger.debug(f"数据加密传输测试异常: {e}")

    @allure.title("测试数据存储安全")
    @allure.description("检查数据存储是否安全")
    def test_data_storage_security(self):
        """测试数据存储安全"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 测试文件上传接口
        upload_endpoints = [
            '/api/v1/file/upload',
            '/api/v1/image/upload',
            '/api/v1/video/upload',
            '/api/v1/face/upload'
        ]
        
        for endpoint in upload_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                
                # 测试文件上传
                test_files = {
                    'file': ('test.txt', 'This is a test file', 'text/plain'),
                    'image': ('test.jpg', b'fake_image_data', 'image/jpeg')
                }
                
                for file_key, file_data in test_files.items():
                    files = {file_key: file_data}
                    response = self.session.post(url, files=files, timeout=10)
                    
                    if response.status_code == 200:
                        # 检查上传后的文件访问权限
                        response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                        
                        if 'file_url' in response_data or 'file_path' in response_data:
                            file_url = response_data.get('file_url') or response_data.get('file_path')
                            
                            # 尝试直接访问上传的文件
                            file_response = self.session.get(file_url, timeout=10)
                            if file_response.status_code == 200:
                                # 检查是否有访问控制
                                if 'access-control' not in file_response.headers.get('cache-control', '').lower():
                                    self._log_privacy_violation(
                                        "文件访问控制",
                                        f"上传的文件 {file_url} 缺少访问控制",
                                        "MEDIUM"
                                    )
            
            except Exception as e:
                logger.debug(f"数据存储安全测试异常: {e}")

    @allure.title("测试日志隐私保护")
    @allure.description("检查日志中是否包含敏感信息")
    def test_log_privacy_protection(self):
        """测试日志隐私保护"""
        allure.dynamic.severity(allure.severity_level.MEDIUM)
        
        # 日志相关接口
        log_endpoints = [
            '/api/v1/log/list',
            '/api/v1/log/download',
            '/api/v1/error/logs',
            '/api/v1/debug/logs',
            '/api/v1/system/logs'
        ]
        
        for endpoint in log_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    response_text = response.text
                    
                    # 检查日志中是否包含敏感信息
                    sensitive_log_patterns = [
                        r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+',
                        r'token["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+',
                        r'secret["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+',
                        r'key["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+',
                        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                        r'(\+?86)?1[3-9]\d{9}'
                    ]
                    
                    for pattern in sensitive_log_patterns:
                        matches = re.findall(pattern, response_text, re.IGNORECASE)
                        if matches:
                            self._log_privacy_violation(
                                "日志敏感信息",
                                f"在 {endpoint} 日志中发现敏感信息: {matches[:3]}",
                                "MEDIUM"
                            )
            
            except Exception as e:
                logger.debug(f"日志隐私保护测试异常: {e}")

    @allure.title("测试API响应数据最小化")
    @allure.description("检查API是否遵循数据最小化原则")
    def test_api_response_minimization(self):
        """测试API响应数据最小化"""
        allure.dynamic.severity(allure.severity_level.MEDIUM)
        
        # 测试用户信息接口
        user_endpoints = [
            '/api/v1/user/info',
            '/api/v1/user/profile',
            '/api/v1/user/list'
        ]
        
        for endpoint in user_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                    
                    # 检查是否返回了不必要的敏感字段
                    unnecessary_fields = [
                        'password', 'password_hash', 'secret', 'private_key',
                        'internal_id', 'system_id', 'debug_info', 'raw_data'
                    ]
                    
                    response_str = str(response_data).lower()
                    for field in unnecessary_fields:
                        if field in response_str:
                            self._log_privacy_violation(
                                "数据最小化违规",
                                f"在 {endpoint} 中返回了不必要的字段: {field}",
                                "LOW"
                            )
            
            except Exception as e:
                logger.debug(f"API响应数据最小化测试异常: {e}")

    @allure.title("测试数据匿名化")
    @allure.description("检查敏感数据是否正确匿名化")
    def test_data_anonymization(self):
        """测试数据匿名化"""
        allure.dynamic.severity(allure.severity_level.MEDIUM)
        
        # 测试分析数据接口
        analytics_endpoints = [
            '/api/v1/analytics/users',
            '/api/v1/analytics/behavior',
            '/api/v1/analytics/statistics',
            '/api/v1/reports/users'
        ]
        
        for endpoint in analytics_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = self.session.get(url, timeout=10)
                
                if response.status_code == 200:
                    response_text = response.text
                    
                    # 检查是否包含可识别的个人信息
                    identifiable_patterns = [
                        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # 邮箱
                        r'(\+?86)?1[3-9]\d{9}',  # 手机号
                        r'\d{17}[\dXx]',  # 身份证
                        r'user["\']?\s*[:=]\s*["\']?[^"\'\s,}]+["\']?'  # 用户名
                    ]
                    
                    for pattern in identifiable_patterns:
                        matches = re.findall(pattern, response_text, re.IGNORECASE)
                        if matches:
                            self._log_privacy_violation(
                                "数据匿名化不足",
                                f"在 {endpoint} 中发现可识别信息: {matches[:3]}",
                                "MEDIUM"
                            )
            
            except Exception as e:
                logger.debug(f"数据匿名化测试异常: {e}")

    @allure.title("生成数据隐私报告")
    @allure.description("生成数据隐私保护测试报告")
    def test_generate_privacy_report(self):
        """生成数据隐私报告"""
        allure.dynamic.severity(allure.severity_level.NORMAL)
        
        # 生成隐私测试摘要
        total_violations = len(self.privacy_violations)
        critical_violations = len([v for v in self.privacy_violations if v['severity'] == 'CRITICAL'])
        high_violations = len([v for v in self.privacy_violations if v['severity'] == 'HIGH'])
        medium_violations = len([v for v in self.privacy_violations if v['severity'] == 'MEDIUM'])
        
        report = f"""
数据隐私保护测试报告
==================

测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
目标系统: {self.base_url}

隐私违规统计:
- 总计: {total_violations}
- 严重: {critical_violations}
- 高危: {high_violations}
- 中危: {medium_violations}

详细违规列表:
"""
        
        for violation in self.privacy_violations:
            report += f"- [{violation['severity']}] {violation['test']}: {violation['description']}\n"
        
        # 添加隐私保护建议
        report += """

隐私保护建议:
============
1. 实施数据最小化原则，只收集必要的数据
2. 对敏感数据进行加密存储和传输
3. 实施访问控制和权限管理
4. 定期进行数据匿名化处理
5. 建立数据泄露监控机制
6. 实施数据保留期限管理
7. 提供用户数据删除功能
8. 定期进行隐私影响评估
"""
        
        allure.attach(report, name="数据隐私保护测试报告", attachment_type=allure.attachment_type.TEXT)
        
        # 如果有严重或高危漏洞，测试失败
        if critical_violations > 0 or high_violations > 0:
            pytest.fail(f"发现隐私保护漏洞: {critical_violations}个严重, {high_violations}个高危")


