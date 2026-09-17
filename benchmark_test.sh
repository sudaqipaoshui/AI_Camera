#!/bin/bash

# X5芯片基准测试快速运行脚本

# 定义Python脚本路径
PYTHON_SCRIPT="Benchmark/test_x5_benchmark_standalone.py"
GUIDE_DOC="Benchmark/README.md"

echo "============================================================"
echo "X5芯片基准测试快速运行脚本"
echo "============================================================"

# 检查Python 3是否安装
if ! command -v python3 &> /dev/null
then
    echo "错误: python3 未安装。请安装 Python 3.8 或更高版本。"
    exit 1
fi

# 检查必要的Python库
echo "检查Python依赖..."
REQUIRED_LIBS=("paramiko" "matplotlib" "numpy")
for lib in "${REQUIRED_LIBS[@]}"; do
    python3 -c "import $lib" &> /dev/null
    if [ $? -ne 0 ]; then
        echo "警告: 缺少 Python 库 '$lib'。正在尝试安装..."
        pip install "$lib"
        if [ $? -ne 0 ]; then
            echo "错误: 无法安装 Python 库 '$lib'。请手动安装或检查网络连接。"
            exit 1
        fi
    fi
done
echo "所有Python依赖已安装。"

# 检查Python脚本是否存在
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "错误: Python 脚本 '$PYTHON_SCRIPT' 未找到。请确保脚本在当前目录下。"
    exit 1
fi

# 检查使用指南文档是否存在
if [ ! -f "$GUIDE_DOC" ]; then
    echo "警告: 使用指南文档 '$GUIDE_DOC' 未找到。"
fi

echo "------------------------------------------------------------"
echo "开始运行X5芯片基准测试..."
echo "------------------------------------------------------------"

# 解析命令行参数（配置类型）
CONFIG_TYPE="${1:-standard}"

echo "使用配置类型: $CONFIG_TYPE"
echo "可用配置:"
echo "  quick     - 快速测试 (5分钟)"
echo "  standard  - 标准测试 (15分钟，默认)"
echo "  extended  - 扩展测试 (30分钟)"
echo "  stress    - 压力测试 (60分钟)"
echo ""

# 运行Python脚本，传递配置参数
python3 "$PYTHON_SCRIPT" "$CONFIG_TYPE"

# 检查Python脚本的退出状态
if [ $? -eq 0 ]; then
    echo "------------------------------------------------------------"
    echo "X5芯片基准测试成功完成！"
    echo "详细报告和图表已生成在 'allure-report/' 目录下。"
    echo "------------------------------------------------------------"
else
    echo "------------------------------------------------------------"
    echo "X5芯片基准测试失败。请查看上面的错误信息。"
    echo "详细报告和图表已生成在 'allure-report/' 目录下。"
    echo "------------------------------------------------------------"
    exit 1
fi


