#!/bin/bash
# X5摄像头AI模型性能测试快速运行脚本

echo "============================================================"
echo "X5摄像头AI模型性能测试"
echo "============================================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3，请先安装Python 3"
    exit 1
fi

# 检查依赖库
echo "检查依赖库..."
python3 -c "import paramiko, matplotlib, numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "错误: 缺少必要的依赖库，请先安装："
    echo "pip3 install paramiko matplotlib numpy"
    exit 1
fi

# 检查脚本文件
if [ ! -f "Performance/test_all_models_performance.py" ]; then
    echo "错误: 未找到测试脚本 Performance/test_all_models_performance.py"
    exit 1
fi

# 运行测试
echo "开始运行模型性能测试..."
echo ""

python3 Performance/test_all_models_performance.py

# 检查运行结果
if [ $? -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "测试完成！请查看生成的报告文件。"
    echo "============================================================"
else
    echo ""
    echo "============================================================"
    echo "测试失败！请检查错误信息。"
    echo "============================================================"
    exit 1
fi
