#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI摄像头认证安全测试

测试内容：
- 认证绕过攻击测试
- 弱密码检测
- 会话管理安全
- 多因素认证测试
- 认证令牌安全
"""

import allure
import pytest
import requests
import time
import hashlib
import base64
import json
import re
from urllib.parse import urljoin
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@allure.feature('security')
@allure.story('authentication-security')
class TestAuthenticationSecurity:
    """认证安全测试类"""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, env):
        """测试环境初始化"""
        self.env = env
        self.base_url = self.env.get('host', {}).get('camera', 'http://192.168.2.119')
        self.session = requests.Session()
        self.security_violations = []
        
        # 常见弱密码列表
        self.weak_passwords = [
            '123456', 'password', 'admin', 'root', '12345678',
            'qwerty', 'abc123', 'password123', 'admin123',
            '1234567890', 'letmein', 'welcome', 'monkey'
        ]
        
        # 常见用户名列表
        self.common_usernames = [
            'admin', 'root', 'user', 'test', 'guest', 'demo',
            'administrator', 'operator', 'camera', 'device'
        ]

    def _log_security_violation(self, test_name, description, severity="HIGH"):
        """记录安全违规"""
        violation = {
            'test': test_name,
            'description': description,
            'severity': severity,
            'timestamp': time.time()
        }
        self.security_violations.append(violation)
        logger.warning(f"安全违规: {test_name} - {description}")

    @allure.title("测试认证绕过攻击")
    @allure.description("测试是否存在认证绕过漏洞")
    def test_authentication_bypass(self):
        """测试认证绕过攻击"""
        allure.dynamic.severity(allure.severity_level.CRITICAL)
        
        # 测试直接访问需要认证的接口
        protected_endpoints = [
            '/api/v1/device/info',
            '/api/v1/camera/status',
            '/api/v1/settings/config',
            '/api/v1/face/data',
            '/api/v1/control/reboot'
        ]
        
        bypass_attempts = [
            # 无认证头
            {},
            # 空认证头
            {'Authorization': ''},
            # 无效认证头
            {'Authorization': 'Bearer invalid_token'},
            {'Authorization': 'Basic invalid'},
            # 尝试绕过认证的参数
            {'X-Forwarded-For': '127.0.0.1'},
            {'X-Real-IP': '127.0.0.1'},
            {'X-Originating-IP': '127.0.0.1'},
            # SQL注入尝试
            {'Authorization': "Bearer ' OR '1'='1"},
            {'Authorization': "Basic ' OR '1'='1"},
        ]
        
        for endpoint in protected_endpoints:
            url = urljoin(self.base_url, endpoint)
            
            for attempt in bypass_attempts:
                try:
                    response = self.session.get(url, headers=attempt, timeout=10)
                    
                    # 检查是否成功绕过认证
                    if response.status_code == 200:
                        self._log_security_violation(
                            "认证绕过",
                            f"成功绕过认证访问 {endpoint}，使用头: {attempt}",
                            "CRITICAL"
                        )
                        allure.attach(
                            f"绕过认证成功\n端点: {endpoint}\n请求头: {attempt}\n响应: {response.text}",
                            name="认证绕过成功",
                            attachment_type=allure.attachment_type.TEXT
                        )
                    
                except Exception as e:
                    logger.debug(f"认证绕过测试异常: {e}")

    @allure.title("测试弱密码攻击")
    @allure.description("测试系统是否使用弱密码")
    def test_weak_password_attack(self):
        """测试弱密码攻击"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        login_endpoints = [
            '/api/v1/auth/login',
            '/api/v1/user/login',
            '/api/v1/login',
            '/login'
        ]
        
        for endpoint in login_endpoints:
            url = urljoin(self.base_url, endpoint)
            
            for username in self.common_usernames:
                for password in self.weak_passwords:
                    try:
                        # 尝试不同的登录方式
                        login_data = {
                            'username': username,
                            'password': password
                        }
                        
                        response = self.session.post(url, json=login_data, timeout=10)
                        
                        # 检查是否登录成功
                        if response.status_code == 200:
                            try:
                                response_data = response.json()
                                if 'token' in response_data or 'success' in response_data:
                                    self._log_security_violation(
                                        "弱密码攻击",
                                        f"使用弱密码登录成功: {username}:{password}",
                                        "HIGH"
                                    )
                                    allure.attach(
                                        f"弱密码登录成功\n用户名: {username}\n密码: {password}\n响应: {response.text}",
                                        name="弱密码攻击成功",
                                        attachment_type=allure.attachment_type.TEXT
                                    )
                            except json.JSONDecodeError:
                                # 非JSON响应，检查是否包含成功标识
                                if any(keyword in response.text.lower() for keyword in ['success', 'welcome', 'dashboard']):
                                    self._log_security_violation(
                                        "弱密码攻击",
                                        f"使用弱密码登录成功: {username}:{password}",
                                        "HIGH"
                                    )
                    
                    except Exception as e:
                        logger.debug(f"弱密码攻击测试异常: {e}")

    @allure.title("测试会话管理安全")
    @allure.description("测试会话令牌的安全性和管理")
    def test_session_management(self):
        """测试会话管理安全"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 测试会话固定攻击
        session1 = requests.Session()
        session2 = requests.Session()
        
        # 尝试获取相同的会话ID
        try:
            response1 = session1.get(urljoin(self.base_url, '/api/v1/auth/login'))
            response2 = session2.get(urljoin(self.base_url, '/api/v1/auth/login'))
            
            # 检查会话ID是否可预测
            if 'Set-Cookie' in response1.headers and 'Set-Cookie' in response2.headers:
                cookie1 = response1.headers['Set-Cookie']
                cookie2 = response2.headers['Set-Cookie']
                
                if cookie1 == cookie2:
                    self._log_security_violation(
                        "会话固定",
                        "会话ID不可预测，存在会话固定漏洞",
                        "HIGH"
                    )
        
        except Exception as e:
            logger.debug(f"会话管理测试异常: {e}")

    @allure.title("测试认证令牌安全")
    @allure.description("测试JWT令牌的安全性和有效性")
    def test_token_security(self):
        """测试认证令牌安全"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 测试JWT令牌解析
        test_tokens = [
            # 空令牌
            '',
            # 无效格式
            'invalid_token',
            # 尝试算法混淆攻击
            'eyJhbGciOiJub25lIiwidHlwIjoiSldUIn0.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.',
            # 尝试密钥混淆
            'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c'
        ]
        
        protected_endpoints = [
            '/api/v1/device/info',
            '/api/v1/camera/status'
        ]
        
        for token in test_tokens:
            for endpoint in protected_endpoints:
                url = urljoin(self.base_url, endpoint)
                headers = {'Authorization': f'Bearer {token}'}
                
                try:
                    response = self.session.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        self._log_security_violation(
                            "令牌安全",
                            f"无效令牌成功访问: {endpoint}",
                            "HIGH"
                        )
                
                except Exception as e:
                    logger.debug(f"令牌安全测试异常: {e}")

    @allure.title("测试暴力破解攻击")
    @allure.description("测试系统对暴力破解攻击的防护")
    def test_brute_force_protection(self):
        """测试暴力破解攻击防护"""
        allure.dynamic.severity(allure.severity_level.MEDIUM)
        
        login_url = urljoin(self.base_url, '/api/v1/auth/login')
        failed_attempts = 0
        lockout_detected = False
        
        # 尝试多次登录失败
        for i in range(20):  # 尝试20次
            try:
                login_data = {
                    'username': 'admin',
                    'password': f'wrong_password_{i}'
                }
                
                response = self.session.post(login_url, json=login_data, timeout=5)
                
                if response.status_code == 429:  # Too Many Requests
                    lockout_detected = True
                    break
                elif response.status_code == 401 or response.status_code == 403:
                    failed_attempts += 1
                elif response.status_code == 200:
                    # 意外成功
                    self._log_security_violation(
                        "暴力破解防护",
                        f"第{i+1}次尝试意外成功",
                        "HIGH"
                    )
                    break
                
                time.sleep(0.1)  # 短暂延迟
                
            except Exception as e:
                logger.debug(f"暴力破解测试异常: {e}")
        
        # 检查是否有防护机制
        if not lockout_detected and failed_attempts >= 10:
            self._log_security_violation(
                "暴力破解防护",
                f"未检测到暴力破解防护机制，{failed_attempts}次失败尝试未被阻止",
                "MEDIUM"
            )

    @allure.title("测试密码策略")
    @allure.description("测试密码复杂度要求")
    def test_password_policy(self):
        """测试密码策略"""
        allure.dynamic.severity(allure.severity_level.MEDIUM)
        
        # 测试弱密码是否被接受
        weak_passwords = [
            '123',           # 太短
            'password',      # 常见密码
            '12345678',      # 纯数字
            'abcdefgh',      # 纯字母
            'PASSWORD',      # 全大写
            'password123'    # 简单组合
        ]
        
        register_url = urljoin(self.base_url, '/api/v1/user/register')
        
        for password in weak_passwords:
            try:
                register_data = {
                    'username': f'test_user_{int(time.time())}',
                    'password': password,
                    'email': f'test{int(time.time())}@example.com'
                }
                
                response = self.session.post(register_url, json=register_data, timeout=10)
                
                if response.status_code == 200:
                    self._log_security_violation(
                        "密码策略",
                        f"弱密码被接受: {password}",
                        "MEDIUM"
                    )
            
            except Exception as e:
                logger.debug(f"密码策略测试异常: {e}")

    @allure.title("生成安全测试报告")
    @allure.description("生成认证安全测试报告")
    def test_generate_security_report(self):
        """生成安全测试报告"""
        allure.dynamic.severity(allure.severity_level.NORMAL)
        
        # 生成安全测试摘要
        total_violations = len(self.security_violations)
        critical_violations = len([v for v in self.security_violations if v['severity'] == 'CRITICAL'])
        high_violations = len([v for v in self.security_violations if v['severity'] == 'HIGH'])
        medium_violations = len([v for v in self.security_violations if v['severity'] == 'MEDIUM'])
        
        report = f"""
认证安全测试报告
================

测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
目标系统: {self.base_url}

安全违规统计:
- 总计: {total_violations}
- 严重: {critical_violations}
- 高危: {high_violations}
- 中危: {medium_violations}

详细违规列表:
"""
        
        for violation in self.security_violations:
            report += f"- [{violation['severity']}] {violation['test']}: {violation['description']}\n"
        
        allure.attach(report, name="认证安全测试报告", attachment_type=allure.attachment_type.TEXT)
        
        # 如果有严重或高危漏洞，测试失败
        if critical_violations > 0 or high_violations > 0:
            pytest.fail(f"发现安全漏洞: {critical_violations}个严重, {high_violations}个高危")


