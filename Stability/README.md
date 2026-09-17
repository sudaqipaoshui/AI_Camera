# 稳定性测试模块


```bash
# 口令从项目根 .env 读取, 不写在命令行里(避免进入 shell 历史 / 进程列表)
set -a; . ./.env; set +a
sshpass -p "$CAMERA_SSH_PASSWORD" ssh -o StrictHostKeyChecking=no root@192.168.2.60

python3 -m pytest Stability/test_x5_ssh_24h_monitoring.py
python3 Stability/generate_report_from_csv.py allure-report/24h-monitoring/<日期>/ssh_monitoring_data.csv
```

```python
# 1. 新建tmux会话
tmux new -s monitoring

# 2. 在tmux会话中运行脚本
python3 /home/rm/Desktop/zhangzhoupan/Stability/test_x5_ssh_24h_monitoring.py

# 3. 按 Ctrl+B，然后按 D 分离会话（detach）
# 现在脚本会在后台继续运行，你可以安全断开SSH

# 4. 重新连接时查看会话
tmux list-sessions
# 或
tmux ls

# 5. 重新附加到会话
tmux attach -t monitoring

# 6. 如果要结束会话，在会话中按 Ctrl+D 或输入 exit
```

## 📋 模块概述

稳定性测试模块提供了对X5摄像头长期稳定性的全面监控和测试，包括24小时SSH监控、硬件状态监控、视频性能监控等。

## 🎯 测试功能

### 1. 24小时SSH监控
- ✅ 硬件状态持续监控
- ✅ 视频性能实时监控
- ✅ 异常检测和告警
- ✅ 数据记录和分析
- ✅ 报告生成和可视化

### 2. 硬件监控
- ✅ CPU使用率监控
- ✅ 内存使用率监控
- ✅ 磁盘使用率监控
- ✅ 温度监控
- ✅ 系统负载监控
- ✅ 网络连接监控

### 3. 视频性能监控
- ✅ FPS（帧率）监控
- ✅ 码率监控
- ✅ 分辨率监控
- ✅ GOP配置监控
- ✅ 延迟监控
- ✅ 视频质量分数

### 4. 日志分析
- ✅ 系统日志解析
- ✅ 摄像头日志分析
- ✅ 错误日志统计
- ✅ 性能日志提取

## 🚀 运行测试

### 运行24小时监控测试
```bash
python -m pytest Stability/test_x5_ssh_24h_monitoring.py -v
```

### 生成监控报告
```bash
# 生成完整监控报告
python Stability/generate_report_from_csv.py allure-report/24h-monitoring/*/ssh_monitoring_data.csv

# 修复CSV数据格式
python Stability/smart_csv_fixer.py

# 修复FPS图表显示
python Stability/fix_fps_chart.py

# 修复视频性能监控FPS
python Stability/fix_video_performance_fps.py
```

## 📁 目录结构

```
Stability/
├── test_x5_ssh_24h_monitoring.py    # 24小时监控测试
├── generate_report_from_csv.py      # 监控报告生成
├── smart_csv_fixer.py               # CSV数据修复工具
├── fix_fps_chart.py                 # FPS图表修复工具
├── fix_video_performance_fps.py     # 视频性能FPS修复工具
└── README.md                        # 本文档
```

## 📊 监控指标

### 1. 硬件监控指标
- **CPU使用率**: 0-100%
- **内存使用率**: 0-100%
- **磁盘使用率**: 0-100%
- **温度**: 摄氏度
- **系统负载**: 1分钟、5分钟、15分钟平均值
- **进程数量**: 总进程数、TCP连接数

### 2. 视频性能指标
- **FPS**: 帧率（估算FPS + 真实FPS）
- **码率**: 视频编码码率（kbps）
- **分辨率**: 视频分辨率（4K/2K/720p）
- **GOP**: 关键帧间隔
- **延迟**: 网络延迟（ms）
- **质量分数**: 视频质量评分

### 3. 摄像头状态指标
- **摄像头进程数**: 运行中的摄像头进程
- **X5进程数**: 运行中的X5相关进程
- **设备数量**: 摄像头设备数量
- **模块数量**: 摄像头模块数量

## 🔧 配置说明

### 1. 监控配置
```python
MONITORING_CONFIG = {
    "ssh": {
        "host": "192.168.1.100",
        "username": "admin",
        "password": "password",
        "port": 22,
        "timeout": 30
    },
    "monitoring": {
        "interval": 300,  # 监控间隔（秒）
        "duration": 86400,  # 监控持续时间（秒）
        "log_dir": "/userdata/deploy/log"
    },
    "thresholds": {
        "temperature": 80,    # 温度阈值（°C）
        "cpu_usage": 95,     # CPU使用率阈值（%）
        "memory_usage": 90,  # 内存使用率阈值（%）
        "disk_usage": 90,    # 磁盘使用率阈值（%）
        "fps_min": 20        # 最小FPS阈值
    }
}
```

### 2. 报告配置
```python
REPORT_CONFIG = {
    "output_dir": "allure-report/24h-monitoring",
    "chart_size": (15, 25),
    "time_format": "%H:%M",
    "time_interval": 4,  # 时间轴间隔（小时）
    "dpi": 300
}
```

## 📈 测试报告

### 1. 监控图表
生成10个监控图表（5x2布局）：
1. **温度监控**: 系统温度变化趋势
2. **CPU监控**: CPU使用率变化趋势
3. **内存监控**: 内存使用率变化趋势
4. **磁盘监控**: 磁盘使用率变化趋势
5. **FPS监控**: 视频帧率变化趋势
6. **进程监控**: 摄像头进程数量变化
7. **码率监控**: 视频码率变化趋势
8. **延迟监控**: 网络延迟变化趋势
9. **日志监控**: 摄像头日志数据统计
10. **视频性能**: 分辨率、FPS、GOP综合监控

### 2. 统计报告
- 硬件统计信息
- 视频性能统计
- 异常检测结果
- 监控汇总报告

### 3. 报告文件
- `ssh_monitoring_charts.png` - 监控图表
- `ssh_monitoring_data.csv` - 监控数据
- `monitoring_statistics_report.txt` - 统计报告
- `monitoring_summary_report.txt` - 汇总报告

## 🛠️ 工具脚本

### 1. 报告生成工具 (`generate_report_from_csv.py`)
- 解析CSV监控数据
- 生成监控图表
- 计算统计信息
- 检测异常情况

### 2. 数据修复工具 (`smart_csv_fixer.py`)
- 修复CSV数据格式
- 处理缺失数据
- 验证数据完整性
- 优化数据质量

### 3. 图表修复工具
- `fix_fps_chart.py` - 修复FPS图表显示问题
- `fix_video_performance_fps.py` - 修复视频性能监控FPS问题

## 📊 数据流程

### 1. 数据收集
```
SSH连接 → 执行监控命令 → 解析返回数据 → 存储到CSV文件
```

### 2. 数据处理
```
读取CSV数据 → 数据清洗 → 异常检测 → 统计分析
```

### 3. 报告生成
```
数据可视化 → 图表生成 → 统计计算 → 报告输出
```

## 🚨 异常检测

### 1. 硬件异常
- 温度超过阈值（>80°C）
- CPU使用率过高（>95%）
- 内存使用率过高（>90%）
- 磁盘使用率过高（>90%）

### 2. 性能异常
- FPS过低（<20）
- 码率异常
- 延迟过高
- 视频质量下降

### 3. 系统异常
- SSH连接失败
- 进程异常退出
- 日志错误增多
- 网络连接异常

## 🔧 开发指南

### 1. 添加新监控指标
```python
def collect_new_metric(self):
    """收集新的监控指标"""
    try:
        # 执行监控命令
        result = self._execute_ssh_command("your_command")
        
        # 解析数据
        value = self._parse_metric_value(result)
        
        # 验证数据
        if self._validate_metric(value):
            return value
        else:
            return None
    except Exception as e:
        logger.error(f"收集新指标失败: {e}")
        return None
```

### 2. 添加新异常检测
```python
def detect_new_anomaly(self, data):
    """检测新的异常情况"""
    if data['new_metric'] > threshold:
        return {
            'type': 'new_anomaly',
            'message': '新指标异常',
            'value': data['new_metric'],
            'threshold': threshold
        }
    return None
```

### 3. 添加新图表
```python
def create_new_chart(self, ax, data, timestamps):
    """创建新图表"""
    ax.plot(timestamps, data, 'color', linewidth=2, label='新指标')
    ax.set_title('新指标监控')
    ax.set_ylabel('单位')
    ax.legend()
    ax.grid(True, alpha=0.3)
```

## 📞 支持

如有问题或建议，请：
1. 查看监控日志
2. 检查配置文件
3. 运行修复工具
4. 创建Issue反馈
