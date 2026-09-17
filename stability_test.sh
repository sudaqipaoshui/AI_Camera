#!/bin/bash
# X5摄像头24小时稳定性监控测试快速运行脚本

# 手动执行参考(口令从 .env 读取, 不要写进命令里, 避免进入 shell 历史和进程列表)
#   set -a; . ./.env; set +a
#   sshpass -p "$CAMERA_SSH_PASSWORD" ssh -o StrictHostKeyChecking=no root@192.168.2.60
#   python3 -m pytest Stability/test_x5_ssh_24h_monitoring.py
#   python3 Stability/generate_report_from_csv.py allure-report/<批次目录>/ssh_monitoring_data.csv


echo "============================================================"
echo "X5摄像头24小时SSH稳定性监控测试"
echo "============================================================"

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到python3，请先安装Python 3"
    exit 1
fi

# 检查依赖库
echo "检查依赖库..."
python3 -c "import paramiko, matplotlib, numpy, pandas, pytest, allure" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "警告: 缺少部分依赖库，正在安装..."
    pip3 install -r requirements.txt
    if [ $? -ne 0 ]; then
        echo "错误: 依赖库安装失败，请手动安装："
        echo "pip3 install paramiko matplotlib numpy pandas pytest allure-pytest"
        exit 1
    fi
fi

# 检查测试脚本
if [ ! -f "Stability/test_x5_ssh_24h_monitoring.py" ]; then
    echo "错误: 未找到测试脚本 Stability/test_x5_ssh_24h_monitoring.py"
    exit 1
fi

# 检查配置文件
if [ ! -f "config/test/camera.yaml" ]; then
    echo "警告: 未找到配置文件 config/test/camera.yaml"
    echo "请确保配置文件存在并包含SSH连接信息"
fi

# 创建输出目录
mkdir -p allure-report/24h-monitoring

# 解析命令行参数
MONITOR_DURATION="${1:-24}"  # 默认24小时
COLLECT_INTERVAL="${2:-60}"   # 默认60秒
ENV_TYPE="${3:-test}"         # 默认test环境

echo ""
echo "监控配置:"
echo "  监控时长: ${MONITOR_DURATION} 小时"
echo "  收集间隔: ${COLLECT_INTERVAL} 秒"
echo "  测试环境: ${ENV_TYPE}"
echo ""

# 询问用户确认（长时间监控需要确认）
if [ "${MONITOR_DURATION}" -ge 12 ]; then
    echo "警告: 这将运行 ${MONITOR_DURATION} 小时的监控测试"
    read -p "确认继续? (y/n): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "已取消"
        exit 0
    fi
fi

# 运行测试
echo "开始运行24小时稳定性监控测试..."
echo ""
echo "提示:"
echo "  - 测试将运行 ${MONITOR_DURATION} 小时"
echo "  - 数据将保存到 allure-report/24h-monitoring/"
echo "  - 可以随时按 Ctrl+C 提前结束测试"
echo ""

# 使用pytest运行测试（从项目根目录运行）
cd "$(dirname "$0")"
python3 -m pytest Stability/test_x5_ssh_24h_monitoring.py \
    -v \
    -m x5_ssh_24h_monitoring \
    --env=${ENV_TYPE} \
    --config=camera.yaml \
    --alluredir=allure-report/allure-results \
    -s

# 检查运行结果
TEST_EXIT_CODE=$?

if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "============================================================"
    echo "测试完成！"
    echo "============================================================"
    echo ""
    echo "生成的报告文件:"
    echo "  - allure-report/24h-monitoring/*/ssh_monitoring_charts.png"
    echo "  - allure-report/24h-monitoring/*/ssh_monitoring_data.csv"
    echo ""
    echo "查看Allure报告:"
    echo "  allure serve allure-report/allure-results"
    echo ""
else
    echo ""
    echo "============================================================"
    echo "测试失败或中断！"
    echo "============================================================"
    echo ""
    echo "请检查:"
    echo "  1. SSH连接是否正常"
    echo "  2. 配置文件是否正确"
    echo "  3. 查看错误日志"
    echo ""
    exit 1
fi

