#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI摄像头网络安全测试

测试内容：
- SSL/TLS配置安全
- 端口扫描和开放服务检测
- 网络协议安全
- 中间人攻击防护
- 网络流量分析
"""

import allure
import pytest
import requests
import socket
import ssl
import subprocess
import time
import json
import re
from urllib.parse import urljoin, urlparse
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@allure.feature('security')
@allure.story('network-security')
class TestNetworkSecurity:
    """网络安全测试类"""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, env):
        """测试环境初始化"""
        self.env = env
        self.base_url = self.env.get('host', {}).get('camera', 'http://192.168.2.119')
        self.parsed_url = urlparse(self.base_url)
        self.host = self.parsed_url.hostname
        self.port = self.parsed_url.port or (443 if self.parsed_url.scheme == 'https' else 80)
        self.security_violations = []

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

    @allure.title("测试SSL/TLS配置安全")
    @allure.description("检查SSL/TLS配置是否存在安全漏洞")
    def test_ssl_tls_security(self):
        """测试SSL/TLS配置安全"""
        allure.dynamic.severity(allure.severity_level.CRITICAL)
        
        if self.parsed_url.scheme != 'https':
            logger.info("目标使用HTTP协议，跳过SSL/TLS测试")
            return
        
        try:
            # 创建SSL上下文
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            # 连接到SSL服务
            with socket.create_connection((self.host, self.port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=self.host) as ssock:
                    # 获取SSL证书信息
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    # 检查SSL版本
                    if version in ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1']:
                        self._log_security_violation(
                            "SSL/TLS版本",
                            f"使用不安全的SSL/TLS版本: {version}",
                            "CRITICAL"
                        )
                    
                    # 检查加密套件
                    if cipher and len(cipher) >= 3:
                        cipher_name = cipher[0]
                        if 'RC4' in cipher_name or 'DES' in cipher_name or 'MD5' in cipher_name:
                            self._log_security_violation(
                                "弱加密套件",
                                f"使用弱加密套件: {cipher_name}",
                                "HIGH"
                            )
                    
                    # 检查证书有效期
                    if cert:
                        import datetime
                        not_after = datetime.datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                        if not_after < datetime.datetime.now():
                            self._log_security_violation(
                                "证书过期",
                                f"SSL证书已过期: {cert['notAfter']}",
                                "HIGH"
                            )
                        
                        # 检查证书有效期是否过长
                        not_before = datetime.datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
                        validity_days = (not_after - not_before).days
                        if validity_days > 365 * 3:  # 超过3年
                            self._log_security_violation(
                                "证书有效期过长",
                                f"证书有效期过长: {validity_days}天",
                                "MEDIUM"
                            )
        
        except Exception as e:
            logger.error(f"SSL/TLS测试异常: {e}")

    @allure.title("测试端口扫描")
    @allure.description("扫描开放端口和服务")
    def test_port_scanning(self):
        """测试端口扫描"""
        allure.dynamic.severity(allure.severity_level.MEDIUM)
        
        # 常见危险端口
        dangerous_ports = {
            21: 'FTP',
            22: 'SSH',
            23: 'Telnet',
            25: 'SMTP',
            53: 'DNS',
            80: 'HTTP',
            135: 'RPC',
            139: 'NetBIOS',
            443: 'HTTPS',
            445: 'SMB',
            993: 'IMAPS',
            995: 'POP3S',
            1433: 'MSSQL',
            3306: 'MySQL',
            3389: 'RDP',
            5432: 'PostgreSQL',
            5900: 'VNC',
            6379: 'Redis',
            8080: 'HTTP-Alt',
            8443: 'HTTPS-Alt'
        }
        
        open_ports = []
        
        for port, service in dangerous_ports.items():
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((self.host, port))
                sock.close()
                
                if result == 0:
                    open_ports.append((port, service))
                    logger.info(f"发现开放端口: {port} ({service})")
            
            except Exception as e:
                logger.debug(f"端口扫描异常 {port}: {e}")
        
        # 检查是否有不必要的开放端口
        unnecessary_ports = [21, 23, 135, 139, 445, 1433, 3306, 3389, 5432, 5900, 6379]
        for port, service in open_ports:
            if port in unnecessary_ports:
                self._log_security_violation(
                    "不必要开放端口",
                    f"发现不必要的开放端口: {port} ({service})",
                    "MEDIUM"
                )
        
        allure.attach(
            f"开放端口列表:\n" + "\n".join([f"{port} - {service}" for port, service in open_ports]),
            name="端口扫描结果",
            attachment_type=allure.attachment_type.TEXT
        )

    @allure.title("测试HTTP安全头")
    @allure.description("检查HTTP安全头配置")
    def test_http_security_headers(self):
        """测试HTTP安全头"""
        allure.dynamic.severity(allure.severity_level.MEDIUM)
        
        required_headers = {
            'Strict-Transport-Security': 'HSTS头缺失',
            'X-Content-Type-Options': '内容类型嗅探防护缺失',
            'X-Frame-Options': '点击劫持防护缺失',
            'X-XSS-Protection': 'XSS防护缺失',
            'Content-Security-Policy': '内容安全策略缺失',
            'Referrer-Policy': '引用策略缺失'
        }
        
        try:
            response = requests.get(self.base_url, timeout=10)
            
            for header, description in required_headers.items():
                if header not in response.headers:
                    self._log_security_violation(
                        "HTTP安全头",
                        f"{description}",
                        "MEDIUM"
                    )
                else:
                    # 检查安全头值是否合理
                    value = response.headers[header]
                    if header == 'X-Frame-Options' and value.lower() not in ['deny', 'sameorigin']:
                        self._log_security_violation(
                            "HTTP安全头",
                            f"X-Frame-Options值不安全: {value}",
                            "LOW"
                        )
            
            # 检查服务器信息泄露
            server_header = response.headers.get('Server', '')
            if server_header and len(server_header) > 0:
                # 检查是否泄露版本信息
                if re.search(r'\d+\.\d+', server_header):
                    self._log_security_violation(
                        "信息泄露",
                        f"服务器头泄露版本信息: {server_header}",
                        "LOW"
                    )
        
        except Exception as e:
            logger.error(f"HTTP安全头测试异常: {e}")

    @allure.title("测试SQL注入攻击")
    @allure.description("测试API接口是否存在SQL注入漏洞")
    def test_sql_injection(self):
        """测试SQL注入攻击"""
        allure.dynamic.severity(allure.severity_level.CRITICAL)
        
        # SQL注入测试载荷
        sql_payloads = [
            "' OR '1'='1",
            "' OR 1=1--",
            "'; DROP TABLE users; --",
            "' UNION SELECT * FROM users--",
            "' OR '1'='1' AND '1'='1",
            "1' OR '1'='1",
            "admin'--",
            "admin'/*",
            "' OR 1=1#",
            "') OR ('1'='1"
        ]
        
        # 测试参数
        test_params = ['id', 'user_id', 'device_id', 'camera_id', 'name', 'username']
        
        # 测试GET参数
        for param in test_params:
            for payload in sql_payloads:
                try:
                    url = f"{self.base_url}/api/v1/device/info?{param}={payload}"
                    response = requests.get(url, timeout=10)
                    
                    # 检查响应中是否包含数据库错误信息
                    error_patterns = [
                        r'mysql_fetch_array',
                        r'ORA-\d+',
                        r'Microsoft.*ODBC.*SQL Server',
                        r'SQLServer JDBC Driver',
                        r'PostgreSQL.*ERROR',
                        r'Warning.*mysql_',
                        r'valid MySQL result',
                        r'MySqlClient\.',
                        r'SQL syntax.*MySQL',
                        r'Warning.*pg_',
                        r'valid PostgreSQL result'
                    ]
                    
                    for pattern in error_patterns:
                        if re.search(pattern, response.text, re.IGNORECASE):
                            self._log_security_violation(
                                "SQL注入",
                                f"发现SQL注入漏洞，参数: {param}, 载荷: {payload}",
                                "CRITICAL"
                            )
                            allure.attach(
                                f"SQL注入成功\n参数: {param}\n载荷: {payload}\n响应: {response.text}",
                                name="SQL注入攻击",
                                attachment_type=allure.attachment_type.TEXT
                            )
                            break
                
                except Exception as e:
                    logger.debug(f"SQL注入测试异常: {e}")

    @allure.title("测试XSS攻击")
    @allure.description("测试跨站脚本攻击漏洞")
    def test_xss_attack(self):
        """测试XSS攻击"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # XSS测试载荷
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<svg onload=alert('XSS')>",
            "<iframe src=javascript:alert('XSS')>",
            "<body onload=alert('XSS')>",
            "<input onfocus=alert('XSS') autofocus>",
            "<select onfocus=alert('XSS') autofocus>",
            "<textarea onfocus=alert('XSS') autofocus>",
            "<keygen onfocus=alert('XSS') autofocus>"
        ]
        
        # 测试参数
        test_params = ['name', 'username', 'description', 'comment', 'search']
        
        for param in test_params:
            for payload in xss_payloads:
                try:
                    # 测试GET参数
                    url = f"{self.base_url}/api/v1/device/info?{param}={payload}"
                    response = requests.get(url, timeout=10)
                    
                    # 检查响应中是否包含未转义的脚本
                    if payload in response.text:
                        self._log_security_violation(
                            "XSS漏洞",
                            f"发现XSS漏洞，参数: {param}, 载荷: {payload}",
                            "HIGH"
                        )
                        allure.attach(
                            f"XSS攻击成功\n参数: {param}\n载荷: {payload}\n响应: {response.text}",
                            name="XSS攻击",
                            attachment_type=allure.attachment_type.TEXT
                        )
                
                except Exception as e:
                    logger.debug(f"XSS测试异常: {e}")

    @allure.title("测试CSRF攻击")
    @allure.description("测试跨站请求伪造漏洞")
    def test_csrf_attack(self):
        """测试CSRF攻击"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 需要CSRF保护的接口
        csrf_endpoints = [
            '/api/v1/device/reboot',
            '/api/v1/settings/update',
            '/api/v1/user/delete',
            '/api/v1/camera/control'
        ]
        
        for endpoint in csrf_endpoints:
            try:
                url = urljoin(self.base_url, endpoint)
                
                # 尝试POST请求（模拟CSRF攻击）
                response = requests.post(url, json={'test': 'csrf'}, timeout=10)
                
                # 检查是否缺少CSRF保护
                if response.status_code == 200:
                    # 检查响应头中是否有CSRF令牌
                    csrf_headers = ['X-CSRF-Token', 'X-CSRFToken', 'X-Requested-With']
                    has_csrf_protection = any(header in response.headers for header in csrf_headers)
                    
                    if not has_csrf_protection:
                        self._log_security_violation(
                            "CSRF漏洞",
                            f"接口缺少CSRF保护: {endpoint}",
                            "HIGH"
                        )
            
            except Exception as e:
                logger.debug(f"CSRF测试异常: {e}")

    @allure.title("测试目录遍历攻击")
    @allure.description("测试目录遍历漏洞")
    def test_directory_traversal(self):
        """测试目录遍历攻击"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 目录遍历载荷
        traversal_payloads = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\drivers\\etc\\hosts',
            '....//....//....//etc/passwd',
            '%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd',
            '..%252f..%252f..%252fetc%252fpasswd',
            '..%c0%af..%c0%af..%c0%afetc%c0%afpasswd'
        ]
        
        # 测试文件下载接口
        file_endpoints = [
            '/api/v1/file/download',
            '/api/v1/log/download',
            '/api/v1/backup/download',
            '/download',
            '/files'
        ]
        
        for endpoint in file_endpoints:
            for payload in traversal_payloads:
                try:
                    url = f"{self.base_url}{endpoint}?file={payload}"
                    response = requests.get(url, timeout=10)
                    
                    # 检查是否成功读取系统文件
                    if 'root:' in response.text or 'bin:' in response.text:
                        self._log_security_violation(
                            "目录遍历",
                            f"发现目录遍历漏洞: {endpoint}",
                            "HIGH"
                        )
                        allure.attach(
                            f"目录遍历成功\n端点: {endpoint}\n载荷: {payload}\n响应: {response.text[:500]}",
                            name="目录遍历攻击",
                            attachment_type=allure.attachment_type.TEXT
                        )
                        break
                
                except Exception as e:
                    logger.debug(f"目录遍历测试异常: {e}")

    @allure.title("生成网络安全报告")
    @allure.description("生成网络安全测试报告")
    def test_generate_network_security_report(self):
        """生成网络安全报告"""
        allure.dynamic.severity(allure.severity_level.NORMAL)
        
        # 生成安全测试摘要
        total_violations = len(self.security_violations)
        critical_violations = len([v for v in self.security_violations if v['severity'] == 'CRITICAL'])
        high_violations = len([v for v in self.security_violations if v['severity'] == 'HIGH'])
        medium_violations = len([v for v in self.security_violations if v['severity'] == 'MEDIUM'])
        
        report = f"""
网络安全测试报告
================

测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
目标系统: {self.base_url}
目标主机: {self.host}:{self.port}

安全违规统计:
- 总计: {total_violations}
- 严重: {critical_violations}
- 高危: {high_violations}
- 中危: {medium_violations}

详细违规列表:
"""
        
        for violation in self.security_violations:
            report += f"- [{violation['severity']}] {violation['test']}: {violation['description']}\n"
        
        allure.attach(report, name="网络安全测试报告", attachment_type=allure.attachment_type.TEXT)
        
        # 如果有严重或高危漏洞，测试失败
        if critical_violations > 0 or high_violations > 0:
            pytest.fail(f"发现安全漏洞: {critical_violations}个严重, {high_violations}个高危")


