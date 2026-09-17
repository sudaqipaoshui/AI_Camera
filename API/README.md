# API功能测试模块

## 📋 模块概述

API功能测试模块提供了对X5摄像头各种API接口的全面测试，包括控制功能、人脸识别、运动项目、RTSP流媒体、系统设置等。

## 🎯 测试功能

### 1. 控制功能测试 (`control/`)
- ✅ 传感器连接检查
- ✅ 代码下载功能
- ✅ 版本信息获取
- ✅ 日志级别设置
- ✅ 系统重启
- ✅ 文件上传
- ✅ 系统更新

### 2. 人脸功能测试 (`face/`)
- ✅ 人脸特征提取
- ✅ 人脸数据清理
- ✅ 人脸模式设置
- ✅ 访客模式测试
- ✅ 人脸同步信息

### 3. 运动项目测试 (`items/`)
- ✅ 运动项目切换
- ✅ 项目配置管理
- ✅ 角色设置
- ✅ 区域设置
- ✅ 手势开关
- ✅ 项目列表获取

### 4. RTSP功能测试 (`rtsp/`)
- ✅ 分辨率切换
- ✅ 摄像头缩放控制
- ✅ 镜像控制
- ✅ 环境模式设置
- ✅ 文件上传
- ✅ 摄像头参数设置
- ✅ RTSP设置管理

### 5. 系统设置测试 (`settings/`)
- ✅ 全局配置管理
- ✅ 设备信息获取
- ✅ 主机信息管理
- ✅ 用户登录测试
- ✅ 网络连通性测试
- ✅ 项目列表管理

### 6. 稳定性测试 (`stability/`)
- ✅ 摄像头稳定性测试
- ✅ 网络稳定性测试
- ✅ 压力操作测试
- ✅ 24小时稳定性评估

### 7. E2E端到端测试 (`e2e/`)
- ✅ 完整测试流程自动化
- ✅ 日志管理（ADB、SSH）
- ✅ 设备操作（APP自动化、SSH重启）
- ✅ 日志分析（APP日志、相机日志）
- ✅ 测试报告生成

## 🚀 运行测试

### 运行所有API测试
```bash
python -m pytest API/tests/ -v
```

### 运行特定模块测试
```bash
# 控制功能测试
python -m pytest API/tests/control/ -v

# 人脸功能测试
python -m pytest API/tests/face/ -v

# 运动项目测试
python -m pytest API/tests/items/ -v

# RTSP功能测试
python -m pytest API/tests/rtsp/ -v

# 系统设置测试
python -m pytest API/tests/settings/ -v

# 稳定性测试
python -m pytest API/tests/stability/ -v

# E2E端到端测试
python -m pytest API/tests/e2e/ -v
```

### 运行特定测试用例
```bash
# 运行单个测试文件
python -m pytest API/tests/control/test_reboot.py -v

# 运行特定测试方法
python -m pytest API/tests/control/test_reboot.py::TestReboot::test_reboot_success -v

# 运行E2E测试套件（使用脚本）
./.vscode/run.sh
```

## 📁 目录结构

```
API/
├── conftest.py                 # 测试配置和fixture
├── API/data/                      # 测试数据文件
│   ├── control/               # 控制功能测试数据
│   ├── face/                  # 人脸功能测试数据
│   ├── items/                 # 运动项目测试数据
│   ├── race/                  # 比赛功能测试数据
│   ├── rtsp/                  # RTSP功能测试数据
│   ├── settings/              # 系统设置测试数据
│   └── stability/             # 稳定性测试数据
└── tests/                     # 测试用例
    ├── control/               # 控制功能测试用例
    ├── face/                  # 人脸功能测试用例
    ├── items/                 # 运动项目测试用例
    ├── performance/           # 性能测试用例
    ├── race/                  # 比赛功能测试用例
    ├── rtsp/                  # RTSP功能测试用例
    ├── security/              # 安全测试用例
    ├── settings/              # 系统设置测试用例
    ├── stability/             # 稳定性测试用例
    ├── e2e/                   # E2E端到端测试用例
    └── test_camera_get_face_sync_info.py
```

## 📊 测试数据

### 1. YAML测试数据格式
```yaml
test_name: "测试名称"
description: "测试描述"
request:
  method: "POST"
  url: "/api/endpoint"
  headers:
    Content-Type: "application/json"
  data:
    param1: "value1"
    param2: "value2"
expected:
  status_code: 200
  response:
    success: true
    message: "操作成功"
```

### 2. 测试用例结构
```python
import pytest
from pytest_helper.http_client import HTTPClient

class TestExample:
    def test_example_success(self, env):
        """测试示例成功场景"""
        client = HTTPClient(env)
        response = client.post("/api/endpoint", data={"param": "value"})
        assert response.status_code == 200
        assert response.json()["success"] is True
```

## 🔧 配置说明

### 1. 环境配置
在 `conftest.py` 中配置测试环境：
```python
@pytest.fixture(scope="session")
def env():
    return {
        "host": "192.168.1.100",
        "username": "admin",
        "password": "password",
        "port": 22
    }
```

### 2. 测试数据配置
在 `API/data/` 目录下的YAML文件中定义测试数据，支持：
- 参数化测试
- 多场景测试
- 边界值测试
- 异常情况测试

## 📈 测试报告

### 1. Allure报告
运行测试后会在 `allure-report/` 目录生成详细的测试报告：
- 测试用例执行结果
- 失败用例详细信息
- 测试覆盖率统计
- 性能指标分析

### 2. 测试标记
使用pytest标记对测试进行分类：
```python
@pytest.mark.smoke
def test_basic_functionality():
    """冒烟测试"""
    pass

@pytest.mark.regression
def test_complex_scenario():
    """回归测试"""
    pass
```

## 🔌 E2E测试辅助插件

`pytest_helper/e2e_helper.py` 插件提供了E2E测试中的通用功能抽象，可以大幅简化测试脚本。

### 插件功能

- **日志管理**：删除、获取ADB和SSH日志
- **设备操作**：SSH重启、APP自动化操作
- **文件管理**：打包、清理日志目录
- **日志分析**：APP日志分析、相机日志分析
- **时间处理**：时间解析、计算、转换

### 使用Fixture

插件提供了以下pytest fixtures，可以直接在测试方法中使用：

```python
def test_example(self, e2e_log_manager, e2e_device_manager, 
                 e2e_file_manager, e2e_log_analyzer, project_root):
    # 使用插件功能
    pass
```

### 快速开始

#### 1. 删除日志
```python
def test_delete_logs(self, env, e2e_log_manager):
    """删除设备上的日志文件"""
    e2e_log_manager.delete_adb_logs(env)
    e2e_log_manager.delete_ssh_logs(env)
```

#### 2. 获取日志
```python
def test_get_log(self, env, e2e_log_manager, project_root):
    """获取APP日志和摄像头日志"""
    e2e_log_manager.get_all_logs(env, project_root)
```

#### 3. APP操作
```python
def test_click_start_button(self, e2e_device_manager, project_root):
    """通过Airtest自动化点击发令按钮"""
    e2e_device_manager.run_sport_test(
        project_root=project_root,
        app_package="com.dreamsport.aicamera.client",
        time_interval=300,
        t2=600,
        time_interval_2=900
    )
```

#### 4. 日志分析
```python
def test_analyze_log(self, e2e_log_analyzer, project_root):
    """统一分析APP和Camera日志"""
    result = e2e_log_analyzer.analyze_all_logs(
        project_root=project_root,
        app_start_time='2025-12-09 14:28:28',
        app_end_time='2025-12-09 14:33:28',
        expected_circles=4,
        distance=800,
        circles=4,
        fallback_start_time='2025-12-09 14:28:28',
        fallback_end_time='2025-12-09 14:33:28'
    )
    
    # 打印漏圈率统计
    if result.get('app_result') and 'stats' in result['app_result']:
        stats = result['app_result']['stats']
        print(f"总人数: {stats['total_people']}")
        print(f"完成4圈: {stats['completed_count']} 人")
        print(f"漏圈率: {stats['missing_rate']:.2f}%")
```

### 完整示例

参考 `API/tests/e2e/test_run_20251117_800m_4r_wtzx_03_plugin.py` 文件，查看完整的使用示例。

### 插件优势

1. **代码简化**：测试方法代码量减少60-70%
2. **自动报告**：所有操作自动附加到Allure报告
3. **统一日志**：统一的日志输出格式
4. **错误处理**：统一的错误处理和异常管理
5. **易于维护**：通用功能集中管理，修改更方便

### 前置要求

确保已安装必要的工具：
- `adb` (Android Debug Bridge)
- `sshpass` (用于SSH密码认证)
- `airtest` (用于APP自动化)
- `allure` (用于生成测试报告)

详细使用说明请参考：`API/pytest_helper/README_E2E_HELPER.md`

## 🛠️ 开发指南

### 1. 添加新测试用例
1. 在对应模块目录下创建测试文件
2. 遵循命名规范：`test_*.py`
3. 使用pytest框架编写测试用例
4. 添加适当的测试数据和断言

### 2. 添加新测试数据
1. 在 `API/data/` 目录下创建YAML文件
2. 定义测试场景和预期结果
3. 使用参数化测试加载数据
4. 确保数据覆盖各种场景

### 3. 测试用例最佳实践
- 使用描述性的测试方法名
- 添加详细的文档字符串
- 使用适当的断言
- 处理异常情况
- 清理测试数据

### 4. E2E测试开发
- 使用 `e2e_helper` 插件简化代码
- 遵循插件提供的fixture模式
- 利用插件自动化的日志分析和报告生成
- 参考现有E2E测试用例的结构

## 🚨 常见问题

### 1. 连接问题
- 检查摄像头IP地址和端口
- 确认网络连通性
- 验证认证信息

### 2. 测试失败
- 查看详细错误信息
- 检查测试数据格式
- 验证API接口状态

### 3. 性能问题
- 调整超时设置
- 优化测试数据
- 使用并发测试

## 📞 支持

如有问题或建议，请：
1. 查看测试日志
2. 检查配置文件
3. 创建Issue反馈
