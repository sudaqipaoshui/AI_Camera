# 基准测试模块

## 📋 模块概述

基准测试模块提供了对X5摄像头性能基准的全面测试，包括CPU性能、NPU推理性能、视频流性能、系统稳定性等基准测试。


执行

# 标准配置（默认，15分钟）
./benchmark_test.sh

# 快速测试（5分钟）
./benchmark_test.sh quick

# 扩展测试（30分钟）
./benchmark_test.sh extended

# 压力测试（60分钟）
./benchmark_test.sh stress


## 🎯 测试功能

### 1. X5芯片基准测试
- ✅ CPU性能基准测试
- ✅ NPU推理性能测试
- ✅ 内存性能测试
- ✅ 视频流性能测试
- ✅ 系统稳定性测试

### 2. 性能基准测试
- ✅ 单核性能测试
- ✅ 多核性能测试
- ✅ 并发性能测试
- ✅ 压力测试
- ✅ 长时间稳定性测试

### 3. 硬件基准测试
- ✅ CPU频率测试
- ✅ 内存带宽测试
- ✅ 存储性能测试
- ✅ 网络性能测试
- ✅ 功耗测试

### 4. 视频基准测试
- ✅ 视频编码性能
- ✅ 视频解码性能
- ✅ 视频流处理性能
- ✅ 帧率测试
- ✅ 延迟测试

## 🚀 运行测试

### 运行所有基准测试
```bash
python -m pytest Benchmark/ -v
```

### 运行特定基准测试
```bash
# X5基准测试
python -m pytest Benchmark/test_x5_benchmark.py -v

# 独立基准测试
python -m pytest Benchmark/test_x5_benchmark_standalone.py -v
```

### 使用脚本运行
```bash
# 运行基准测试脚本
./run_x5_benchmark.sh
```

## 📁 目录结构

```
Benchmark/
├── test_x5_benchmark.py              # X5基准测试
├── test_x5_benchmark_standalone.py  # 独立基准测试
├── benchmark_time_config.py          # 基准测试时间配置
├── adjust_benchmark_time.py         # 基准测试时间调整工具
└── README.md                         # 本文档
```

## 📊 测试指标

### 1. CPU性能指标
- **单核性能**: 单核CPU性能分数
- **多核性能**: 多核CPU性能分数
- **频率**: CPU运行频率（MHz）
- **温度**: CPU运行温度（°C）
- **功耗**: CPU功耗消耗（W）

### 2. NPU性能指标
- **推理时间**: 单次推理耗时（ms）
- **吞吐量**: 每秒推理次数
- **准确率**: 推理准确率（%）
- **内存占用**: NPU内存使用（MB）
- **利用率**: NPU利用率（%）

### 3. 视频性能指标
- **编码性能**: 视频编码速度（fps）
- **解码性能**: 视频解码速度（fps）
- **码率**: 视频码率（kbps）
- **分辨率**: 视频分辨率
- **延迟**: 端到端延迟（ms）

### 4. 系统性能指标
- **启动时间**: 系统启动时间（s）
- **响应时间**: 系统响应时间（ms）
- **吞吐量**: 系统吞吐量（ops/s）
- **稳定性**: 长时间运行稳定性
- **资源使用**: 系统资源使用率

## 🔧 配置说明

### 1. 基准测试配置
```python
BENCHMARK_CONFIG = {
    "cpu": {
        "test_duration": 60,      # 测试持续时间（秒）
        "threads": [1, 2, 4, 8],  # 测试线程数
        "workloads": ["cpu_intensive", "memory_intensive"]
    },
    "npu": {
        "models": ["face_detection", "face_recognition"],
        "batch_sizes": [1, 2, 4, 8],
        "iterations": 100
    },
    "video": {
        "resolutions": ["720p", "1080p", "4K"],
        "codecs": ["H.264", "H.265"],
        "bitrates": [1000, 2000, 4000, 8000]
    },
    "system": {
        "test_duration": 3600,    # 系统测试持续时间（秒）
        "monitor_interval": 1,    # 监控间隔（秒）
        "thresholds": {
            "cpu_usage": 90,
            "memory_usage": 90,
            "temperature": 85
        }
    }
}
```

### 2. 时间配置 (`benchmark_time_config.py`)
```python
TIME_CONFIG = {
    "warmup_time": 30,        # 预热时间（秒）
    "test_time": 300,         # 测试时间（秒）
    "cooldown_time": 60,      # 冷却时间（秒）
    "interval_time": 10,      # 间隔时间（秒）
    "timeout": 600            # 超时时间（秒）
}
```

## 📈 测试报告

### 1. 基准测试报告格式
测试完成后会生成详细的基准测试报告，包括：
- 性能基准数据
- 性能对比图表
- 性能趋势分析
- 性能优化建议

### 2. 报告文件
- `x5_benchmark_report.txt` - 基准测试文本报告
- `x5_benchmark_data.csv` - 基准测试数据CSV
- `x5_benchmark_dashboard.png` - 基准测试仪表板
- `benchmark_raw_log.txt` - 原始测试日志

## 🛠️ 开发指南

### 1. 添加新基准测试
```python
def test_new_benchmark(self):
    """测试新基准指标"""
    # 准备测试环境
    self.setup_benchmark_environment()
    
    # 预热
    self.warmup_test()
    
    # 执行基准测试
    start_time = time.time()
    result = self.execute_benchmark()
    end_time = time.time()
    
    # 计算性能指标
    performance_score = self.calculate_performance_score(result, end_time - start_time)
    
    # 记录结果
    self.record_benchmark_result(performance_score)
    
    # 验证基准要求
    self.assert_benchmark_requirement(performance_score)
```

### 2. 添加新性能指标
```python
def collect_performance_metrics(self):
    """收集性能指标"""
    metrics = {}
    
    # CPU性能
    metrics['cpu_score'] = self.get_cpu_benchmark_score()
    metrics['cpu_freq'] = self.get_cpu_frequency()
    metrics['cpu_temp'] = self.get_cpu_temperature()
    
    # NPU性能
    metrics['npu_score'] = self.get_npu_benchmark_score()
    metrics['npu_utilization'] = self.get_npu_utilization()
    
    # 视频性能
    metrics['video_score'] = self.get_video_benchmark_score()
    metrics['fps'] = self.get_video_fps()
    
    return metrics
```

### 3. 基准测试最佳实践
- 进行充分的预热和冷却
- 多次测量取平均值
- 监控系统资源使用
- 设置合理的性能阈值
- 记录详细的测试日志

## 📊 性能基准

### 1. 推荐性能指标
- **CPU性能**: > 1000分
- **NPU推理时间**: < 50ms
- **视频编码**: > 30fps (1080p)
- **系统稳定性**: > 99.9%
- **温度**: < 80°C

### 2. 性能等级划分
- **A级**: 优秀（90-100分）
- **B级**: 良好（80-89分）
- **C级**: 一般（70-79分）
- **D级**: 较差（60-69分）
- **F级**: 不合格（<60分）

## 🔧 工具脚本

### 1. 基准测试时间调整 (`adjust_benchmark_time.py`)
调整基准测试的时间配置参数。

```bash
python3 Benchmark/adjust_benchmark_time.py quick    # 快速测试配置
python3 Benchmark/adjust_benchmark_time.py standard  # 标准测试配置
python3 Benchmark/adjust_benchmark_time.py extended  # 扩展测试配置
python3 Benchmark/adjust_benchmark_time.py stress   # 压力测试配置
```

### 2. 基准测试配置 (`benchmark_time_config.py`)
集中管理各种测试的时间参数，支持快速、标准、扩展、压力等多种配置方案。

### 3. 报告清理工具 (`cleanup_benchmark_reports.py`)
清理旧的、空的或重复的基准测试报告。

```bash
# 列出所有报告
python3 Benchmark/cleanup_benchmark_reports.py list
python3 Benchmark/cleanup_benchmark_reports.py list -d  # 详细列表

# 清理空报告（预览）
python3 Benchmark/cleanup_benchmark_reports.py clean

# 删除空报告
python3 Benchmark/cleanup_benchmark_reports.py clean --delete

# 清理旧报告（预览，默认7天前）
python3 Benchmark/cleanup_benchmark_reports.py old
python3 Benchmark/cleanup_benchmark_reports.py old --days=3  # 3天前

# 删除旧报告
python3 Benchmark/cleanup_benchmark_reports.py old --delete
python3 Benchmark/cleanup_benchmark_reports.py old --delete --days=3

# 或使用便捷脚本
./Benchmark/cleanup_reports.sh list              # 列出所有报告
./Benchmark/cleanup_reports.sh clean             # 预览空报告
./Benchmark/cleanup_reports.sh clean delete      # 删除空报告
./Benchmark/cleanup_reports.sh old 7 delete      # 删除7天前的报告
```

## 🚨 常见问题

### 1. 性能不达标
- 检查系统配置
- 优化测试环境
- 调整测试参数
- 检查硬件状态

### 2. 测试超时
- 增加超时时间
- 优化测试逻辑
- 减少测试负载
- 检查系统资源

### 3. 结果不稳定
- 增加测试次数
- 改善测试环境
- 优化测试方法
- 检查系统状态

## 📞 支持

如有问题或建议，请：
1. 查看基准测试日志
2. 检查测试配置
3. 运行性能诊断
4. 创建Issue反馈
