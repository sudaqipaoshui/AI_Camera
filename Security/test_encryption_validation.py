#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI摄像头加密验证测试

测试内容：
- 加密算法强度验证
- 密钥管理安全
- 证书验证
- 加密传输验证
- 数据加密存储验证
"""

import allure
import pytest
import requests
import ssl
import socket
import hashlib
import base64
import json
import time
import re
from urllib.parse import urljoin, urlparse
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@allure.feature('security')
@allure.story('encryption-validation')
class TestEncryptionValidation:
    """加密验证测试类"""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, env):
        """测试环境初始化"""
        self.env = env
        self.base_url = self.env.get('host', {}).get('camera', 'http://192.168.2.119')
        self.parsed_url = urlparse(self.base_url)
        self.host = self.parsed_url.hostname
        self.port = self.parsed_url.port or (443 if self.parsed_url.scheme == 'https' else 80)
        self.encryption_violations = []

    def _log_encryption_violation(self, test_name, description, severity="HIGH"):
        """记录加密违规"""
        violation = {
            'test': test_name,
            'description': description,
            'severity': severity,
            'timestamp': time.time()
        }
        self.encryption_violations.append(violation)
        logger.warning(f"加密违规: {test_name} - {description}")

    @allure.title("测试SSL/TLS加密强度")
    @allure.description("验证SSL/TLS加密算法和密钥长度")
    def test_ssl_tls_encryption_strength(self):
        """测试SSL/TLS加密强度"""
        allure.dynamic.severity(allure.severity_level.CRITICAL)
        
        if self.parsed_url.scheme != 'https':
            self._log_encryption_violation(
                "HTTPS缺失",
                "系统未使用HTTPS加密传输",
                "CRITICAL"
            )
            return
        
        try:
            # 创建SSL上下文
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # 连接到SSL服务
            with socket.create_connection((self.host, self.port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.host) as ssock:
                    # 获取加密信息
                    cipher = ssock.cipher()
                    version = ssock.version()
                    cert = ssock.getpeercert()
                    
                    # 检查TLS版本
                    if version in ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']:
                        self._log_encryption_violation(
                            "弱TLS版本",
                            f"使用不安全的TLS版本: {version}",
                            "CRITICAL"
                        )
                    
                    # 检查加密套件
                    if cipher and len(cipher) >= 3:
                        cipher_name = cipher[0]
                        key_length = cipher[2]
                        
                        # 检查密钥长度
                        if key_length < 128:
                            self._log_encryption_violation(
                                "弱密钥长度",
                                f"使用弱密钥长度: {key_length}位",
                                "CRITICAL"
                            )
                        
                        # 检查弱加密算法
                        weak_ciphers = ['RC4', 'DES', '3DES', 'MD5', 'SHA1']
                        if any(weak in cipher_name for weak in weak_ciphers):
                            self._log_encryption_violation(
                                "弱加密算法",
                                f"使用弱加密算法: {cipher_name}",
                                "HIGH"
                            )
                    
                    # 检查证书信息
                    if cert:
                        # 检查证书算法
                        if 'sha1' in cert.get('signatureAlgorithm', '').lower():
                            self._log_encryption_violation(
                                "弱证书算法",
                                f"使用SHA1签名算法: {cert.get('signatureAlgorithm')}",
                                "HIGH"
                            )
                        
                        # 检查证书密钥长度
                        if 'rsaEncryption' in cert.get('subjectPublicKeyInfo', {}).get('algorithm', {}).get('algorithm', ''):
                            # 这里需要解析公钥长度，简化处理
                            pass
                    
                    allure.attach(
                        f"SSL/TLS信息:\n版本: {version}\n加密套件: {cipher_name if cipher else 'Unknown'}\n密钥长度: {key_length if cipher else 'Unknown'}\n证书: {cert.get('subject', {}) if cert else 'None'}",
                        name="SSL/TLS加密信息",
                        attachment_type=allure.attachment_type.TEXT
                    )
        
        except Exception as e:
            logger.error(f"SSL/TLS加密强度测试异常: {e}")

    @allure.title("测试API数据加密")
    @allure.description("验证API传输的数据是否加密")
    def test_api_data_encryption(self):
        """测试API数据加密"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
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
                
                # 测试POST请求
                test_data = {
                    'username': 'test_user',
                    'password': 'test_password_123',
                    'email': 'test@example.com',
                    'sensitive_data': 'This is sensitive information'
                }
                
                response = requests.post(url, json=test_data, timeout=10)
                
                # 检查响应头中的加密相关信息
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    # 检查响应数据是否包含明文敏感信息
                    response_text = response.text
                    if 'test_password_123' in response_text:
                        self._log_encryption_violation(
                            "明文密码传输",
                            f"在 {endpoint} 中发现明文密码传输",
                            "HIGH"
                        )
                
                # 检查是否使用HTTPS
                if not url.startswith('https://'):
                    self._log_encryption_violation(
                        "非加密传输",
                        f"敏感接口 {endpoint} 未使用HTTPS",
                        "HIGH"
                    )
            
            except Exception as e:
                logger.debug(f"API数据加密测试异常: {e}")

    @allure.title("测试文件加密存储")
    @allure.description("验证上传文件的加密存储")
    def test_file_encryption_storage(self):
        """测试文件加密存储"""
        allure.dynamic.severity(allure.severity_level.MEDIUM)
        
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
                
                # 创建测试文件
                test_content = "This is sensitive test data that should be encrypted"
                test_file = ('test.txt', test_content, 'text/plain')
                
                files = {'file': test_file}
                response = requests.post(url, files=files, timeout=10)
                
                if response.status_code == 200:
                    response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                    
                    # 检查文件URL
                    file_url = response_data.get('file_url') or response_data.get('file_path')
                    if file_url:
                        # 尝试访问上传的文件
                        file_response = requests.get(file_url, timeout=10)
                        if file_response.status_code == 200:
                            # 检查文件内容是否加密
                            if test_content in file_response.text:
                                self._log_encryption_violation(
                                    "文件未加密存储",
                                    f"上传的文件 {file_url} 未加密存储",
                                    "MEDIUM"
                                )
            
            except Exception as e:
                logger.debug(f"文件加密存储测试异常: {e}")

    @allure.title("测试数据库加密")
    @allure.description("验证数据库连接和存储加密")
    def test_database_encryption(self):
        """测试数据库加密"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 测试数据库相关接口
        db_endpoints = [
            '/api/v1/user/info',
            '/api/v1/face/data',
            '/api/v1/analytics/data',
            '/api/v1/settings/config'
        ]
        
        for endpoint in db_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    response_text = response.text
                    
                    # 检查是否泄露数据库连接信息
                    db_patterns = [
                        r'mysql://[^"\s]+',
                        r'postgresql://[^"\s]+',
                        r'mongodb://[^"\s]+',
                        r'jdbc:[^"\s]+',
                        r'connection.*string',
                        r'database.*url',
                        r'db.*host',
                        r'db.*password'
                    ]
                    
                    for pattern in db_patterns:
                        matches = re.findall(pattern, response_text, re.IGNORECASE)
                        if matches:
                            self._log_encryption_violation(
                                "数据库信息泄露",
                                f"在 {endpoint} 中发现数据库连接信息: {matches[:3]}",
                                "HIGH"
                            )
            
            except Exception as e:
                logger.debug(f"数据库加密测试异常: {e}")

    @allure.title("测试密钥管理")
    @allure.description("验证密钥管理和存储安全")
    def test_key_management(self):
        """测试密钥管理"""
        allure.dynamic.severity(allure.severity_level.CRITICAL)
        
        # 测试配置接口
        config_endpoints = [
            '/api/v1/settings/config',
            '/api/v1/system/config',
            '/api/v1/debug/config',
            '/api/v1/admin/config'
        ]
        
        for endpoint in config_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    response_text = response.text
                    
                    # 检查是否泄露密钥信息
                    key_patterns = [
                        r'api[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+["\']?',
                        r'secret[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+["\']?',
                        r'private[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+["\']?',
                        r'access[_-]?token["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+["\']?',
                        r'jwt[_-]?secret["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+["\']?',
                        r'encryption[_-]?key["\']?\s*[:=]\s*["\']?[A-Za-z0-9+/=]+["\']?'
                    ]
                    
                    for pattern in key_patterns:
                        matches = re.findall(pattern, response_text, re.IGNORECASE)
                        if matches:
                            self._log_encryption_violation(
                                "密钥泄露",
                                f"在 {endpoint} 中发现密钥信息: {matches[:3]}",
                                "CRITICAL"
                            )
            
            except Exception as e:
                logger.debug(f"密钥管理测试异常: {e}")

    @allure.title("测试密码哈希")
    @allure.description("验证密码存储是否使用强哈希算法")
    def test_password_hashing(self):
        """测试密码哈希"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 测试用户注册接口
        register_endpoints = [
            '/api/v1/user/register',
            '/api/v1/auth/register',
            '/api/v1/admin/create_user'
        ]
        
        for endpoint in register_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                
                # 尝试注册用户
                test_data = {
                    'username': f'test_user_{int(time.time())}',
                    'password': 'test_password_123',
                    'email': f'test{int(time.time())}@example.com'
                }
                
                response = requests.post(url, json=test_data, timeout=10)
                
                if response.status_code == 200:
                    response_text = response.text
                    
                    # 检查是否返回了明文密码或弱哈希
                    if 'test_password_123' in response_text:
                        self._log_encryption_violation(
                            "明文密码存储",
                            f"在 {endpoint} 中发现明文密码存储",
                            "CRITICAL"
                        )
                    
                    # 检查是否使用弱哈希算法
                    weak_hash_patterns = [
                        r'md5["\']?\s*[:=]\s*["\']?[a-f0-9]{32}["\']?',
                        r'sha1["\']?\s*[:=]\s*["\']?[a-f0-9]{40}["\']?',
                        r'password["\']?\s*[:=]\s*["\']?[a-f0-9]{32}["\']?'  # 可能是MD5
                    ]
                    
                    for pattern in weak_hash_patterns:
                        matches = re.findall(pattern, response_text, re.IGNORECASE)
                        if matches:
                            self._log_encryption_violation(
                                "弱密码哈希",
                                f"在 {endpoint} 中发现弱密码哈希: {matches[:3]}",
                                "HIGH"
                            )
            
            except Exception as e:
                logger.debug(f"密码哈希测试异常: {e}")

    @allure.title("测试加密算法实现")
    @allure.description("验证加密算法的正确实现")
    def test_encryption_algorithm_implementation(self):
        """测试加密算法实现"""
        allure.dynamic.severity(allure.severity_level.MEDIUM)
        
        # 测试加密相关接口
        crypto_endpoints = [
            '/api/v1/crypto/encrypt',
            '/api/v1/crypto/decrypt',
            '/api/v1/data/encrypt',
            '/api/v1/secure/encrypt'
        ]
        
        for endpoint in crypto_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                
                # 测试加密功能
                test_data = {
                    'data': 'This is test data for encryption',
                    'algorithm': 'AES-256-GCM'
                }
                
                response = requests.post(url, json=test_data, timeout=10)
                
                if response.status_code == 200:
                    response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                    
                    # 检查加密结果
                    if 'encrypted_data' in response_data:
                        encrypted_data = response_data['encrypted_data']
                        
                        # 检查加密数据格式
                        if not isinstance(encrypted_data, str) or len(encrypted_data) < 32:
                            self._log_encryption_violation(
                                "加密实现异常",
                                f"在 {endpoint} 中加密结果格式异常",
                                "MEDIUM"
                            )
                        
                        # 检查是否包含原始数据
                        if test_data['data'] in str(response_data):
                            self._log_encryption_violation(
                                "加密泄露",
                                f"在 {endpoint} 中加密后仍包含原始数据",
                                "HIGH"
                            )
            
            except Exception as e:
                logger.debug(f"加密算法实现测试异常: {e}")

    @allure.title("生成加密验证报告")
    @allure.description("生成加密验证测试报告")
    def test_generate_encryption_report(self):
        """生成加密验证报告"""
        allure.dynamic.severity(allure.severity_level.NORMAL)
        
        # 生成加密测试摘要
        total_violations = len(self.encryption_violations)
        critical_violations = len([v for v in self.encryption_violations if v['severity'] == 'CRITICAL'])
        high_violations = len([v for v in self.encryption_violations if v['severity'] == 'HIGH'])
        medium_violations = len([v for v in self.encryption_violations if v['severity'] == 'MEDIUM'])
        
        report = f"""
加密验证测试报告
================

测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
目标系统: {self.base_url}

加密违规统计:
- 总计: {total_violations}
- 严重: {critical_violations}
- 高危: {high_violations}
- 中危: {medium_violations}

详细违规列表:
"""
        
        for violation in self.encryption_violations:
            report += f"- [{violation['severity']}] {violation['test']}: {violation['description']}\n"
        
        # 添加加密安全建议
        report += """

加密安全建议:
============
1. 使用强加密算法（AES-256, RSA-2048+）
2. 实施端到端加密传输
3. 安全存储和管理密钥
4. 使用强密码哈希算法（bcrypt, scrypt, Argon2）
5. 定期更新加密密钥
6. 实施证书管理策略
7. 监控加密操作日志
8. 进行加密安全审计
"""
        
        allure.attach(report, name="加密验证测试报告", attachment_type=allure.attachment_type.TEXT)
        
        # 如果有严重或高危漏洞，测试失败
        if critical_violations > 0 or high_violations > 0:
            pytest.fail(f"发现加密安全漏洞: {critical_violations}个严重, {high_violations}个高危")


