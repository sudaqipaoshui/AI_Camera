#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI摄像头综合安全测试

整合所有安全测试模块，提供一键式安全测试
"""

import allure
import pytest
import requests
import time
import json
from urllib.parse import urljoin
import logging

# 导入安全测试模块
# Security/ 不是 Python 包(无 __init__.py), 因此用同级绝对导入。
# pytest 的 prepend 导入模式会把 Security/ 加入 sys.path, 同级模块可直接 import。
from test_authentication_security import TestAuthenticationSecurity
from test_network_security import TestNetworkSecurity
from test_data_privacy import TestDataPrivacy
from test_encryption_validation import TestEncryptionValidation
from test_access_control import TestAccessControl
from security_test_utils import SecurityTestUtils
from security_config import SECURITY_CONFIG

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@allure.feature('security')
@allure.story('comprehensive-security')
class TestSecurityComprehensive:
    """综合安全测试类"""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, env):
        """测试环境初始化"""
        self.env = env
        self.base_url = self.env.get('host', {}).get('camera', 'http://192.168.2.119')
        self.session = requests.Session()
        self.all_violations = []
        self.test_results = {}

    def _collect_violations(self, violations):
        """收集所有安全违规"""
        self.all_violations.extend(violations)

    @allure.title("执行综合安全测试")
    @allure.description("执行所有安全测试模块并生成综合报告")
    def test_comprehensive_security_scan(self):
        """执行综合安全测试"""
        allure.dynamic.severity(allure.severity_level.CRITICAL)
        
        logger.info("开始执行综合安全测试")
        start_time = time.time()
        
        # 1. 认证安全测试
        with allure.step("执行认证安全测试"):
            try:
                auth_tester = TestAuthenticationSecurity()
                auth_tester.setup(self.env)
                
                # 执行认证测试
                auth_tester.test_authentication_bypass()
                auth_tester.test_weak_password_attack()
                auth_tester.test_session_management()
                auth_tester.test_token_security()
                auth_tester.test_brute_force_protection()
                auth_tester.test_password_policy()
                
                self._collect_violations(auth_tester.security_violations)
                self.test_results['authentication'] = {
                    'status': 'completed',
                    'violations': len(auth_tester.security_violations)
                }
                
                logger.info(f"认证安全测试完成，发现 {len(auth_tester.security_violations)} 个问题")
                
            except Exception as e:
                logger.error(f"认证安全测试异常: {e}")
                self.test_results['authentication'] = {'status': 'failed', 'error': str(e)}

        # 2. 网络安全测试
        with allure.step("执行网络安全测试"):
            try:
                network_tester = TestNetworkSecurity()
                network_tester.setup(self.env)
                
                # 执行网络测试
                network_tester.test_ssl_tls_security()
                network_tester.test_port_scanning()
                network_tester.test_http_security_headers()
                network_tester.test_sql_injection()
                network_tester.test_xss_attack()
                network_tester.test_csrf_attack()
                network_tester.test_directory_traversal()
                
                self._collect_violations(network_tester.security_violations)
                self.test_results['network'] = {
                    'status': 'completed',
                    'violations': len(network_tester.security_violations)
                }
                
                logger.info(f"网络安全测试完成，发现 {len(network_tester.security_violations)} 个问题")
                
            except Exception as e:
                logger.error(f"网络安全测试异常: {e}")
                self.test_results['network'] = {'status': 'failed', 'error': str(e)}

        # 3. 数据隐私保护测试
        with allure.step("执行数据隐私保护测试"):
            try:
                privacy_tester = TestDataPrivacy()
                privacy_tester.setup(self.env)
                
                # 执行隐私测试
                privacy_tester.test_sensitive_data_leakage()
                privacy_tester.test_personal_information_protection()
                privacy_tester.test_data_encryption_transmission()
                privacy_tester.test_data_storage_security()
                privacy_tester.test_log_privacy_protection()
                privacy_tester.test_api_response_minimization()
                privacy_tester.test_data_anonymization()
                
                self._collect_violations(privacy_tester.privacy_violations)
                self.test_results['privacy'] = {
                    'status': 'completed',
                    'violations': len(privacy_tester.privacy_violations)
                }
                
                logger.info(f"数据隐私保护测试完成，发现 {len(privacy_tester.privacy_violations)} 个问题")
                
            except Exception as e:
                logger.error(f"数据隐私保护测试异常: {e}")
                self.test_results['privacy'] = {'status': 'failed', 'error': str(e)}

        # 4. 加密验证测试
        with allure.step("执行加密验证测试"):
            try:
                encryption_tester = TestEncryptionValidation()
                encryption_tester.setup(self.env)
                
                # 执行加密测试
                encryption_tester.test_ssl_tls_encryption_strength()
                encryption_tester.test_api_data_encryption()
                encryption_tester.test_file_encryption_storage()
                encryption_tester.test_database_encryption()
                encryption_tester.test_key_management()
                encryption_tester.test_password_hashing()
                encryption_tester.test_encryption_algorithm_implementation()
                
                self._collect_violations(encryption_tester.encryption_violations)
                self.test_results['encryption'] = {
                    'status': 'completed',
                    'violations': len(encryption_tester.encryption_violations)
                }
                
                logger.info(f"加密验证测试完成，发现 {len(encryption_tester.encryption_violations)} 个问题")
                
            except Exception as e:
                logger.error(f"加密验证测试异常: {e}")
                self.test_results['encryption'] = {'status': 'failed', 'error': str(e)}

        # 5. 访问控制测试
        with allure.step("执行访问控制测试"):
            try:
                access_tester = TestAccessControl()
                access_tester.setup(self.env)
                
                # 执行访问控制测试
                access_tester.test_privilege_escalation()
                access_tester.test_horizontal_privilege_escalation()
                access_tester.test_vertical_privilege_escalation()
                access_tester.test_session_management()
                access_tester.test_role_permission_validation()
                access_tester.test_api_parameter_tampering()
                access_tester.test_direct_object_reference()
                
                self._collect_violations(access_tester.access_violations)
                self.test_results['access_control'] = {
                    'status': 'completed',
                    'violations': len(access_tester.access_violations)
                }
                
                logger.info(f"访问控制测试完成，发现 {len(access_tester.access_violations)} 个问题")
                
            except Exception as e:
                logger.error(f"访问控制测试异常: {e}")
                self.test_results['access_control'] = {'status': 'failed', 'error': str(e)}

        # 生成综合安全报告
        with allure.step("生成综合安全报告"):
            self._generate_comprehensive_report(start_time)

    def _generate_comprehensive_report(self, start_time):
        """生成综合安全报告"""
        end_time = time.time()
        duration = end_time - start_time
        
        # 统计违规信息
        total_violations = len(self.all_violations)
        critical_violations = len([v for v in self.all_violations if v.get('severity') == 'CRITICAL'])
        high_violations = len([v for v in self.all_violations if v.get('severity') == 'HIGH'])
        medium_violations = len([v for v in self.all_violations if v.get('severity') == 'MEDIUM'])
        low_violations = len([v for v in self.all_violations if v.get('severity') == 'LOW'])
        
        # 按测试模块统计
        module_stats = {}
        for violation in self.all_violations:
            test_name = violation.get('test', 'Unknown')
            if test_name not in module_stats:
                module_stats[test_name] = 0
            module_stats[test_name] += 1
        
        # 生成报告
        report = f"""
AI摄像头综合安全测试报告
========================

测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
目标系统: {self.base_url}
测试耗时: {duration:.2f} 秒

测试模块状态:
============
"""
        
        for module, result in self.test_results.items():
            status = result['status']
            if status == 'completed':
                violations = result.get('violations', 0)
                report += f"- {module}: 完成 (发现 {violations} 个问题)\n"
            else:
                error = result.get('error', 'Unknown error')
                report += f"- {module}: 失败 ({error})\n"
        
        report += f"""

安全违规统计:
============
- 总计: {total_violations}
- 严重: {critical_violations}
- 高危: {high_violations}
- 中危: {medium_violations}
- 低危: {low_violations}

按测试类型统计:
==============
"""
        
        for test_name, count in sorted(module_stats.items(), key=lambda x: x[1], reverse=True):
            report += f"- {test_name}: {count} 个问题\n"
        
        report += f"""

详细违规列表:
============
"""
        
        # 按严重程度排序
        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        sorted_violations = sorted(self.all_violations, 
                                 key=lambda x: severity_order.get(x.get('severity', 'LOW'), 3))
        
        for i, violation in enumerate(sorted_violations, 1):
            severity = violation.get('severity', 'UNKNOWN')
            test_name = violation.get('test', 'Unknown Test')
            description = violation.get('description', 'No description')
            report += f"{i:3d}. [{severity}] {test_name}: {description}\n"
        
        # 安全建议
        report += """

安全建议:
========
"""
        
        if critical_violations > 0:
            report += "🚨 发现严重安全漏洞，需要立即修复:\n"
            report += "- 检查认证绕过漏洞\n"
            report += "- 修复SQL注入漏洞\n"
            report += "- 加强权限控制\n"
            report += "- 实施安全编码规范\n\n"
        
        if high_violations > 0:
            report += "⚠️  发现高危安全漏洞，需要优先修复:\n"
            report += "- 加强输入验证\n"
            report += "- 实施XSS防护\n"
            report += "- 加强会话管理\n"
            report += "- 实施CSRF防护\n\n"
        
        if medium_violations > 0:
            report += "📋 发现中危安全问题，建议修复:\n"
            report += "- 配置安全头\n"
            report += "- 加强密码策略\n"
            report += "- 实施数据加密\n"
            report += "- 加强日志记录\n\n"
        
        if total_violations == 0:
            report += "✅ 未发现安全漏洞，系统安全性良好\n\n"
        
        report += """
持续安全监控建议:
================
1. 定期进行安全测试
2. 实施安全代码审查
3. 建立安全事件响应机制
4. 定期更新安全补丁
5. 加强安全培训
6. 实施安全监控和告警
7. 定期进行安全审计
8. 建立安全基线
"""
        
        # 附加报告到Allure
        allure.attach(report, name="综合安全测试报告", attachment_type=allure.attachment_type.TEXT)
        
        # 生成JSON格式的详细报告
        json_report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'target': self.base_url,
            'duration': duration,
            'summary': {
                'total_violations': total_violations,
                'critical': critical_violations,
                'high': high_violations,
                'medium': medium_violations,
                'low': low_violations
            },
            'module_results': self.test_results,
            'violations': self.all_violations,
            'module_stats': module_stats
        }
        
        allure.attach(
            json.dumps(json_report, indent=2, ensure_ascii=False),
            name="综合安全测试报告(JSON)",
            attachment_type=allure.attachment_type.JSON
        )
        
        logger.info(f"综合安全测试完成，共发现 {total_violations} 个安全问题")
        
        # 如果有严重或高危漏洞，测试失败
        if critical_violations > 0 or high_violations > 0:
            pytest.fail(f"发现严重安全漏洞: {critical_violations}个严重, {high_violations}个高危")

    @allure.title("快速安全扫描")
    @allure.description("执行快速安全扫描，检查关键安全问题")
    def test_quick_security_scan(self):
        """快速安全扫描"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        logger.info("开始快速安全扫描")
        
        # 检查基本安全配置
        try:
            response = requests.get(self.base_url, timeout=10)
            
            # 检查HTTPS
            if not self.base_url.startswith('https://'):
                self.all_violations.append({
                    'test': '快速扫描',
                    'description': '系统未使用HTTPS加密传输',
                    'severity': 'HIGH',
                    'timestamp': time.time()
                })
            
            # 检查安全头
            missing_headers = SecurityTestUtils.check_http_security_headers(response)
            for header in missing_headers:
                self.all_violations.append({
                    'test': '快速扫描',
                    'description': header,
                    'severity': 'MEDIUM',
                    'timestamp': time.time()
                })
            
            # 检查敏感数据泄露
            detected_data = SecurityTestUtils.detect_sensitive_data(response.text)
            for data_type, matches in detected_data.items():
                self.all_violations.append({
                    'test': '快速扫描',
                    'description': f'发现敏感数据泄露: {data_type}',
                    'severity': 'HIGH',
                    'timestamp': time.time()
                })
            
            logger.info(f"快速安全扫描完成，发现 {len(self.all_violations)} 个问题")
            
        except Exception as e:
            logger.error(f"快速安全扫描异常: {e}")
            self.all_violations.append({
                'test': '快速扫描',
                'description': f'扫描异常: {str(e)}',
                'severity': 'MEDIUM',
                'timestamp': time.time()
            })
        
        # 生成快速扫描报告
        if self.all_violations:
            report = "快速安全扫描报告\n================\n\n"
            for violation in self.all_violations:
                report += f"- [{violation['severity']}] {violation['description']}\n"
            
            allure.attach(report, name="快速安全扫描报告", attachment_type=allure.attachment_type.TEXT)


