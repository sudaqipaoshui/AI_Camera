# Windows快速入门指南 🪟

## 🎯 3步开始使用

### 步骤1️⃣: 安装依赖（首次使用）

**双击运行**: `install_windows.bat`

或在命令行运行：
```cmd
cd API
install_windows.bat
```

这会自动安装所有需要的Python包。

### 步骤2️⃣: 调试检查（可选）

**双击运行**: `run_windows_debug.bat`

检查项目：
- ✅ Python版本
- ✅ 依赖库
- ✅ WebSocket连接
- ✅ OpenCV功能

### 步骤3️⃣: 运行程序

**双击运行**: `run_crawler_windows.bat`

或在命令行运行：
```cmd
cd API
python crawler_v2.py
```

**停止程序**: 按 `Ctrl+C`

## 📊 查看结果

程序停止后会自动生成报告：

```
allure-report\websocket\20260113\
├── 20260113_172240_report.html  👈 双击打开HTML报告
├── 20260113_172240_report.json
├── videos\
│   └── 20260113_172649.avi
└── logs\
    └── 20260113_172649.log
```

### HTML报告包含：

- 📊 **总体统计**: 帧数、有效率
- 🌡️ **温度监控**: 平均/最低/最高温度
- ⚠️ **警告统计**: 错误和警告详情
- 📈 **性能分析**: FPS、消息大小

## 🌡️ 温度数据说明

- **采集方式**: 从WebSocket消息自动提取
- **字段名称**: `temp`
- **单位转换**: 自动从毫摄氏度转为摄氏度
- **采集频率**: 每帧（约30fps）

### 温度正常范围：
- ✅ **60-75°C**: 正常工作温度
- ⚠️ **75-85°C**: 温度偏高
- 🔥 **>85°C**: 温度过高，需要散热

## ⚙️ 配置修改

### 修改摄像头IP

编辑 `crawler_v2.py` 第39行：
```python
ip = "192.168.2.30"  # 改为你的IP
```

### 禁用视频窗口显示

编辑 `crawler_v2.py`，注释以下行：
```python
# cv2.imshow('AI Camera', img)
# cv2.waitKey(1)
```

## 🐛 常见问题

### ❌ Python未安装

**下载地址**: https://www.python.org/downloads/

**安装注意**: 勾选 "Add Python to PATH"

### ❌ pip安装超时

使用国内镜像：
```cmd
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple websocket-client opencv-python numpy protobuf
```

### ❌ WebSocket连接失败

1. 检查IP地址是否正确
2. 测试网络: `ping 192.168.2.30`
3. 检查防火墙设置

### ❌ 视频无法播放

安装VLC播放器: https://www.videolan.org/vlc/

### ❌ 温度数据为0

1. 查看日志搜索 "🌡️"
2. 确认设备支持温度上报
3. 检查WebSocket消息是否包含 `temp` 字段

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `install_windows.bat` | 一键安装依赖 |
| `run_windows_debug.bat` | 调试检查工具 |
| `run_crawler_windows.bat` | 运行主程序 |
| `crawler_v2.py` | 主程序 |
| `test_windows_debug.py` | 调试脚本 |
| `README_WINDOWS.md` | 详细文档 |
| `QUICKSTART_WINDOWS.md` | 本文档 |

## 💡 使用技巧

### 后台运行

```cmd
start /B python crawler_v2.py > output.log 2>&1
```

### 定时运行

使用Windows任务计划程序：
1. 打开"任务计划程序"
2. 创建基本任务
3. 选择触发器（每天/每周）
4. 操作：启动程序 `run_crawler_windows.bat`

### 查看实时日志

```cmd
# 在另一个命令窗口
cd allure-report\websocket\20260113\logs
type 20260113_HHMMSS.log
```

## 🎓 进阶使用

详细配置和高级功能请查看：
- `README_WINDOWS.md` - 完整文档
- `API/README.md` - API文档

## ✅ 验证环境

快速验证所有依赖是否安装：

```cmd
python -c "import websocket, cv2, numpy, google.protobuf; print('✅ All OK!')"
```

---

**需要帮助?** 查看 `README_WINDOWS.md` 获取详细说明
