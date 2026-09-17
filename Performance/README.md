# 性能测试模块

## 📋 模块概述

性能测试模块提供了对X5摄像头各种性能指标的全面测试，包括模型性能、硬件性能、多模型并发性能等。

## 🎯 测试功能

### 1. 模型性能测试
- ✅ 单模型性能测试
- ✅ 多模型并发测试
- ✅ 模型推理时间测试
- ✅ 模型准确率测试
- ✅ 模型资源占用测试

### 2. 硬件性能监控
- ✅ CPU性能监控
- ✅ 内存使用监控
- ✅ GPU/NPU性能监控
- ✅ 温度监控
- ✅ 功耗监控

### 3. 视频性能测试
- ✅ 视频流性能测试
- ✅ 编码性能测试
- ✅ 解码性能测试
- ✅ 帧率测试
- ✅ 延迟测试

## 🚀 运行测试

### 运行所有性能测试
```bash
python -m pytest Performance/ -v
```

### 运行特定测试
```bash
# 模型性能测试
python -m pytest Performance/test_model_performance.py -v

# 多模型并发测试
python -m pytest Performance/test_all_models_performance.py -v
```

### 使用脚本运行
```bash
# 运行模型性能测试脚本
./run_model_performance_test.sh
```

## 📁 目录结构

```
Performance/
├── test_model_performance.py      # 单模型性能测试
├── test_all_models_performance.py # 多模型并发测试
└── README.md                      # 本文档
```

## 📊 测试指标

### 1. 模型性能指标
- **推理时间**: 单次推理耗时
- **吞吐量**: 每秒处理帧数
- **准确率**: 模型预测准确率
- **内存占用**: 模型运行时内存使用
- **CPU使用率**: 推理时CPU占用

### 2. 硬件性能指标
- **CPU频率**: 各核心运行频率
- **内存使用率**: 系统内存占用百分比
- **温度**: CPU和系统温度
- **功耗**: 系统功耗消耗
- **负载**: 系统负载平均值

### 3. 视频性能指标
- **帧率**: 视频处理帧率
- **码率**: 视频编码码率
- **分辨率**: 视频处理分辨率
- **延迟**: 端到端处理延迟
- **丢帧率**: 视频处理丢帧情况

## 🔧 配置说明

### 1. 模型配置
```python
MODEL_CONFIG = {
    "face_detection": {
        "model_path": "/path/to/face_detection.bin",
        "input_size": (640, 640),
        "batch_size": 1
    },
    "face_recognition": {
        "model_path": "/path/to/face_recognition.bin",
        "input_size": (112, 112),
        "batch_size": 1
    }
}
```

### 2. 性能测试配置
```python
PERFORMANCE_CONFIG = {
    "test_duration": 300,  # 测试持续时间（秒）
    "warmup_duration": 30,  # 预热时间（秒）
    "sample_interval": 1,   # 采样间隔（秒）
    "thresholds": {
        "max_inference_time": 100,  # 最大推理时间（ms）
        "min_fps": 25,              # 最小帧率
        "max_cpu_usage": 80,        # 最大CPU使用率（%）
        "max_memory_usage": 90      # 最大内存使用率（%）
    }
}
```

## 📈 测试报告

### 1. 性能报告格式
测试完成后会生成详细的性能报告，包括：
- 性能指标统计
- 性能趋势图表
- 异常检测结果
- 性能建议

### 2. 报告文件
- `model_performance_report.csv` - 性能数据CSV文件
- `model_performance_charts.png` - 性能趋势图表
- `model_performance_statistics.txt` - 性能统计报告

## 🛠️ 开发指南

### 1. 添加新模型测试
```python
def test_new_model_performance(self):
    """测试新模型性能"""
    model = load_model("new_model.bin")
    
    # 预热
    for _ in range(10):
        model.infer(test_data)
    
    # 性能测试
    start_time = time.time()
    for _ in range(100):
        result = model.infer(test_data)
    end_time = time.time()
    
    # 计算性能指标
    avg_time = (end_time - start_time) / 100
    fps = 1.0 / avg_time
    
    # 断言
    assert avg_time < 0.1  # 平均推理时间小于100ms
    assert fps > 10        # 帧率大于10fps
```

### 2. 添加新性能指标
```python
def collect_performance_metrics(self):
    """收集性能指标"""
    metrics = {}
    
    # CPU性能
    metrics['cpu_usage'] = get_cpu_usage()
    metrics['cpu_freq'] = get_cpu_frequency()
    
    # 内存性能
    metrics['memory_usage'] = get_memory_usage()
    metrics['memory_available'] = get_available_memory()
    
    # 温度
    metrics['temperature'] = get_temperature()
    
    return metrics
```

### 3. 性能测试最佳实践
- 进行充分的预热
- 多次测量取平均值
- 监控系统资源使用
- 设置合理的性能阈值
- 记录详细的性能日志

## 📊 性能基准

### 1. 推荐性能指标
- **推理时间**: < 100ms
- **帧率**: > 25fps
- **CPU使用率**: < 80%
- **内存使用率**: < 90%
- **温度**: < 80°C

### 2. 性能优化建议
- 使用模型量化
- 优化输入数据格式
- 调整批处理大小
- 使用硬件加速
- 优化内存使用

## 🚨 常见问题

### 1. 性能不达标
- 检查模型配置
- 优化输入数据
- 调整系统参数
- 检查硬件状态

### 2. 内存不足
- 减少批处理大小
- 优化模型结构
- 释放不必要的资源
- 增加系统内存

### 3. 温度过高
- 降低CPU频率
- 改善散热条件
- 减少并发任务
- 监控温度变化

## 📞 支持

如有问题或建议，请：
1. 查看性能测试日志
2. 检查系统配置
3. 创建Issue反馈
