#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI摄像头访问控制测试

测试内容：
- 权限提升攻击
- 水平权限绕过
- 垂直权限绕过
- 会话管理测试
- 角色权限验证
"""

import allure
import pytest
import requests
import json
import time
import re
from urllib.parse import urljoin
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@allure.feature('security')
@allure.story('access-control')
class TestAccessControl:
    """访问控制测试类"""

    @pytest.fixture(scope="class", autouse=True)
    def setup(self, env):
        """测试环境初始化"""
        self.env = env
        self.base_url = self.env.get('host', {}).get('camera', 'http://192.168.2.119')
        self.session = requests.Session()
        self.access_violations = []
        
        # 测试用户角色
        self.test_roles = {
            'admin': {'username': 'admin', 'password': 'admin123'},
            'user': {'username': 'user', 'password': 'user123'},
            'guest': {'username': 'guest', 'password': 'guest123'},
            'operator': {'username': 'operator', 'password': 'operator123'}
        }
        
        # 权限级别定义
        self.permission_levels = {
            'public': 0,      # 公开访问
            'user': 1,        # 普通用户
            'operator': 2,    # 操作员
            'admin': 3,       # 管理员
            'super_admin': 4  # 超级管理员
        }

    def _log_access_violation(self, test_name, description, severity="HIGH"):
        """记录访问控制违规"""
        violation = {
            'test': test_name,
            'description': description,
            'severity': severity,
            'timestamp': time.time()
        }
        self.access_violations.append(violation)
        logger.warning(f"访问控制违规: {test_name} - {description}")

    def _login_user(self, role):
        """登录指定角色的用户"""
        try:
            user_info = self.test_roles.get(role)
            if not user_info:
                return None
            
            login_url = urljoin(self.base_url, '/api/v1/auth/login')
            login_data = {
                'username': user_info['username'],
                'password': user_info['password']
            }
            
            response = self.session.post(login_url, json=login_data, timeout=10)
            
            if response.status_code == 200:
                response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                return response_data.get('token') or response_data.get('access_token')
            
            return None
        except Exception as e:
            logger.debug(f"用户登录异常: {e}")
            return None

    @allure.title("测试权限提升攻击")
    @allure.description("测试低权限用户是否能访问高权限功能")
    def test_privilege_escalation(self):
        """测试权限提升攻击"""
        allure.dynamic.severity(allure.severity_level.CRITICAL)
        
        # 高权限功能列表
        admin_endpoints = [
            '/api/v1/admin/users',
            '/api/v1/admin/system',
            '/api/v1/admin/config',
            '/api/v1/admin/logs',
            '/api/v1/admin/backup',
            '/api/v1/admin/restore',
            '/api/v1/admin/delete',
            '/api/v1/admin/reboot'
        ]
        
        # 测试不同角色的权限
        for role in ['guest', 'user', 'operator']:
            token = self._login_user(role)
            if not token:
                continue
            
            # 设置认证头
            headers = {'Authorization': f'Bearer {token}'}
            
            for endpoint in admin_endpoints:
                try:
                    url = urljoin(self.base_url, endpoint)
                    response = self.session.get(url, headers=headers, timeout=10)
                    
                    # 检查是否成功访问高权限功能
                    if response.status_code == 200:
                        self._log_access_violation(
                            "权限提升",
                            f"{role}角色成功访问管理员功能: {endpoint}",
                            "CRITICAL"
                        )
                        allure.attach(
                            f"权限提升成功\n角色: {role}\n端点: {endpoint}\n响应: {response.text}",
                            name="权限提升攻击",
                            attachment_type=allure.attachment_type.TEXT
                        )
                
                except Exception as e:
                    logger.debug(f"权限提升测试异常: {e}")

    @allure.title("测试水平权限绕过")
    @allure.description("测试用户是否能访问其他用户的资源")
    def test_horizontal_privilege_escalation(self):
        """测试水平权限绕过"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 需要水平权限控制的功能
        horizontal_endpoints = [
            '/api/v1/user/profile',
            '/api/v1/user/data',
            '/api/v1/face/features',
            '/api/v1/analytics/personal',
            '/api/v1/settings/personal'
        ]
        
        # 测试不同用户ID
        test_user_ids = ['1', '2', '3', 'admin', 'test', 'user']
        
        for role in ['user', 'operator']:
            token = self._login_user(role)
            if not token:
                continue
            
            headers = {'Authorization': f'Bearer {token}'}
            
            for endpoint in horizontal_endpoints:
                for user_id in test_user_ids:
                    try:
                        # 尝试访问其他用户的资源
                        url = urljoin(self.base_url, f"{endpoint}?user_id={user_id}")
                        response = self.session.get(url, headers=headers, timeout=10)
                        
                        if response.status_code == 200:
                            # 检查是否返回了其他用户的数据
                            response_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
                            
                            # 检查响应中是否包含其他用户的信息
                            if str(user_id) in str(response_data) and user_id != '1':  # 假设用户1是当前用户
                                self._log_access_violation(
                                    "水平权限绕过",
                                    f"{role}角色成功访问用户{user_id}的资源: {endpoint}",
                                    "HIGH"
                                )
                                allure.attach(
                                    f"水平权限绕过成功\n角色: {role}\n目标用户: {user_id}\n端点: {endpoint}\n响应: {response.text}",
                                    name="水平权限绕过",
                                    attachment_type=allure.attachment_type.TEXT
                                )
                    
                    except Exception as e:
                        logger.debug(f"水平权限绕过测试异常: {e}")

    @allure.title("测试垂直权限绕过")
    @allure.description("测试低权限用户是否能执行高权限操作")
    def test_vertical_privilege_escalation(self):
        """测试垂直权限绕过"""
        allure.dynamic.severity(allure.severity_level.CRITICAL)
        
        # 高权限操作列表
        admin_operations = [
            {'method': 'POST', 'endpoint': '/api/v1/admin/create_user', 'data': {'username': 'test', 'password': 'test'}},
            {'method': 'PUT', 'endpoint': '/api/v1/admin/update_user', 'data': {'user_id': '1', 'role': 'admin'}},
            {'method': 'DELETE', 'endpoint': '/api/v1/admin/delete_user', 'data': {'user_id': '2'}},
            {'method': 'POST', 'endpoint': '/api/v1/admin/reboot', 'data': {}},
            {'method': 'POST', 'endpoint': '/api/v1/admin/backup', 'data': {}},
            {'method': 'PUT', 'endpoint': '/api/v1/admin/config', 'data': {'setting': 'value'}}
        ]
        
        for role in ['guest', 'user', 'operator']:
            token = self._login_user(role)
            if not token:
                continue
            
            headers = {'Authorization': f'Bearer {token}'}
            
            for operation in admin_operations:
                try:
                    url = urljoin(self.base_url, operation['endpoint'])
                    
                    if operation['method'] == 'POST':
                        response = self.session.post(url, json=operation['data'], headers=headers, timeout=10)
                    elif operation['method'] == 'PUT':
                        response = self.session.put(url, json=operation['data'], headers=headers, timeout=10)
                    elif operation['method'] == 'DELETE':
                        response = self.session.delete(url, json=operation['data'], headers=headers, timeout=10)
                    
                    # 检查是否成功执行高权限操作
                    if response.status_code == 200:
                        self._log_access_violation(
                            "垂直权限绕过",
                            f"{role}角色成功执行管理员操作: {operation['method']} {operation['endpoint']}",
                            "CRITICAL"
                        )
                        allure.attach(
                            f"垂直权限绕过成功\n角色: {role}\n操作: {operation['method']} {operation['endpoint']}\n响应: {response.text}",
                            name="垂直权限绕过",
                            attachment_type=allure.attachment_type.TEXT
                        )
                
                except Exception as e:
                    logger.debug(f"垂直权限绕过测试异常: {e}")

    @allure.title("测试会话管理安全")
    @allure.description("测试会话令牌的安全性和有效性")
    def test_session_management(self):
        """测试会话管理安全"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 测试会话固定攻击
        session1 = requests.Session()
        session2 = requests.Session()
        
        try:
            # 获取两个不同的会话
            response1 = session1.get(urljoin(self.base_url, '/api/v1/auth/login'))
            response2 = session2.get(urljoin(self.base_url, '/api/v1/auth/login'))
            
            # 检查会话ID是否可预测
            if 'Set-Cookie' in response1.headers and 'Set-Cookie' in response2.headers:
                cookie1 = response1.headers['Set-Cookie']
                cookie2 = response2.headers['Set-Cookie']
                
                if cookie1 == cookie2:
                    self._log_access_violation(
                        "会话固定",
                        "会话ID不可预测，存在会话固定漏洞",
                        "HIGH"
                    )
            
            # 测试会话超时
            token = self._login_user('user')
            if token:
                headers = {'Authorization': f'Bearer {token}'}
                
                # 等待一段时间后测试会话是否仍然有效
                time.sleep(2)
                
                response = self.session.get(urljoin(self.base_url, '/api/v1/user/info'), headers=headers, timeout=10)
                
                # 检查会话是否过期
                if response.status_code == 401:
                    logger.info("会话正确过期")
                elif response.status_code == 200:
                    # 检查会话是否应该过期（这里需要根据实际配置调整）
                    pass
        
        except Exception as e:
            logger.debug(f"会话管理测试异常: {e}")

    @allure.title("测试角色权限验证")
    @allure.description("验证不同角色的权限是否正确实施")
    def test_role_permission_validation(self):
        """测试角色权限验证"""
        allure.dynamic.severity(allure.severity_level.MEDIUM)
        
        # 角色权限矩阵
        role_permissions = {
            'guest': {
                'allowed': ['/api/v1/public/info', '/api/v1/public/status'],
                'denied': ['/api/v1/user/profile', '/api/v1/admin/users']
            },
            'user': {
                'allowed': ['/api/v1/user/profile', '/api/v1/user/data'],
                'denied': ['/api/v1/admin/users', '/api/v1/admin/config']
            },
            'operator': {
                'allowed': ['/api/v1/camera/control', '/api/v1/settings/basic'],
                'denied': ['/api/v1/admin/users', '/api/v1/admin/delete']
            },
            'admin': {
                'allowed': ['/api/v1/admin/users', '/api/v1/admin/config'],
                'denied': []
            }
        }
        
        for role, permissions in role_permissions.items():
            token = self._login_user(role)
            if not token:
                continue
            
            headers = {'Authorization': f'Bearer {token}'}
            
            # 测试允许的权限
            for endpoint in permissions['allowed']:
                try:
                    url = urljoin(self.base_url, endpoint)
                    response = self.session.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 403:
                        self._log_access_violation(
                            "权限不足",
                            f"{role}角色无法访问允许的端点: {endpoint}",
                            "LOW"
                        )
                
                except Exception as e:
                    logger.debug(f"角色权限验证测试异常: {e}")
            
            # 测试拒绝的权限
            for endpoint in permissions['denied']:
                try:
                    url = urljoin(self.base_url, endpoint)
                    response = self.session.get(url, headers=headers, timeout=10)
                    
                    if response.status_code == 200:
                        self._log_access_violation(
                            "权限过度",
                            f"{role}角色可以访问被拒绝的端点: {endpoint}",
                            "HIGH"
                        )
                
                except Exception as e:
                    logger.debug(f"角色权限验证测试异常: {e}")

    @allure.title("测试API参数篡改")
    @allure.description("测试通过修改API参数绕过权限控制")
    def test_api_parameter_tampering(self):
        """测试API参数篡改"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 测试参数篡改攻击
        tampering_tests = [
            {
                'endpoint': '/api/v1/user/profile',
                'params': {'user_id': '1'},
                'tampered_params': {'user_id': '2'}
            },
            {
                'endpoint': '/api/v1/admin/users',
                'params': {'role': 'user'},
                'tampered_params': {'role': 'admin'}
            },
            {
                'endpoint': '/api/v1/settings/config',
                'params': {'level': 'basic'},
                'tampered_params': {'level': 'admin'}
            }
        ]
        
        for role in ['user', 'operator']:
            token = self._login_user(role)
            if not token:
                continue
            
            headers = {'Authorization': f'Bearer {token}'}
            
            for test in tampering_tests:
                try:
                    # 正常请求
                    url = urljoin(self.base_url, test['endpoint'])
                    normal_response = self.session.get(url, params=test['params'], headers=headers, timeout=10)
                    
                    # 篡改参数请求
                    tampered_response = self.session.get(url, params=test['tampered_params'], headers=headers, timeout=10)
                    
                    # 检查篡改后是否获得更高权限
                    if (normal_response.status_code == 403 and tampered_response.status_code == 200) or \
                       (normal_response.status_code == 200 and tampered_response.status_code == 200 and 
                        normal_response.text != tampered_response.text):
                        self._log_access_violation(
                            "参数篡改",
                            f"{role}角色通过参数篡改绕过权限控制: {test['endpoint']}",
                            "HIGH"
                        )
                        allure.attach(
                            f"参数篡改成功\n角色: {role}\n端点: {test['endpoint']}\n原始参数: {test['params']}\n篡改参数: {test['tampered_params']}\n响应: {tampered_response.text}",
                            name="参数篡改攻击",
                            attachment_type=allure.attachment_type.TEXT
                        )
                
                except Exception as e:
                    logger.debug(f"参数篡改测试异常: {e}")

    @allure.title("测试直接对象引用")
    @allure.description("测试直接对象引用攻击")
    def test_direct_object_reference(self):
        """测试直接对象引用攻击"""
        allure.dynamic.severity(allure.severity_level.HIGH)
        
        # 测试直接对象引用
        object_references = [
            {'endpoint': '/api/v1/user/profile', 'id_param': 'user_id', 'ids': ['1', '2', '3', 'admin']},
            {'endpoint': '/api/v1/file/download', 'id_param': 'file_id', 'ids': ['1', '2', '3', 'secret']},
            {'endpoint': '/api/v1/data/export', 'id_param': 'data_id', 'ids': ['1', '2', '3', 'private']}
        ]
        
        for role in ['user', 'guest']:
            token = self._login_user(role)
            if not token:
                continue
            
            headers = {'Authorization': f'Bearer {token}'}
            
            for ref_test in object_references:
                for obj_id in ref_test['ids']:
                    try:
                        url = urljoin(self.base_url, f"{ref_test['endpoint']}?{ref_test['id_param']}={obj_id}")
                        response = self.session.get(url, headers=headers, timeout=10)
                        
                        if response.status_code == 200:
                            # 检查是否访问了不应该访问的对象
                            if obj_id != '1':  # 假设ID为1是当前用户的对象
                                self._log_access_violation(
                                    "直接对象引用",
                                    f"{role}角色通过直接对象引用访问ID {obj_id} 的对象: {ref_test['endpoint']}",
                                    "HIGH"
                                )
                                allure.attach(
                                    f"直接对象引用成功\n角色: {role}\n端点: {ref_test['endpoint']}\n对象ID: {obj_id}\n响应: {response.text}",
                                    name="直接对象引用攻击",
                                    attachment_type=allure.attachment_type.TEXT
                                )
                    
                    except Exception as e:
                        logger.debug(f"直接对象引用测试异常: {e}")

    @allure.title("生成访问控制报告")
    @allure.description("生成访问控制测试报告")
    def test_generate_access_control_report(self):
        """生成访问控制报告"""
        allure.dynamic.severity(allure.severity_level.NORMAL)
        
        # 生成访问控制测试摘要
        total_violations = len(self.access_violations)
        critical_violations = len([v for v in self.access_violations if v['severity'] == 'CRITICAL'])
        high_violations = len([v for v in self.access_violations if v['severity'] == 'HIGH'])
        medium_violations = len([v for v in self.access_violations if v['severity'] == 'MEDIUM'])
        
        report = f"""
访问控制测试报告
================

测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}
目标系统: {self.base_url}

访问控制违规统计:
- 总计: {total_violations}
- 严重: {critical_violations}
- 高危: {high_violations}
- 中危: {medium_violations}

详细违规列表:
"""
        
        for violation in self.access_violations:
            report += f"- [{violation['severity']}] {violation['test']}: {violation['description']}\n"
        
        # 添加访问控制建议
        report += """

访问控制建议:
============
1. 实施基于角色的访问控制(RBAC)
2. 使用最小权限原则
3. 实施细粒度的权限控制
4. 定期审计用户权限
5. 实施会话管理和超时机制
6. 使用安全的认证和授权机制
7. 实施API访问控制
8. 监控和记录访问日志
"""
        
        allure.attach(report, name="访问控制测试报告", attachment_type=allure.attachment_type.TEXT)
        
        # 如果有严重或高危漏洞，测试失败
        if critical_violations > 0 or high_violations > 0:
            pytest.fail(f"发现访问控制漏洞: {critical_violations}个严重, {high_violations}个高危")


