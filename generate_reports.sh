#!/bin/bash

# 自动报告生成脚本
# 在生成报告前自动修复CSV格式问题

set -e  # 遇到错误时退出

# 确保使用bash运行（而不是sh）
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取日期参数
DATE=${1:-$(date +%Y-%m-%d)}

echo -e "${BLUE}=== X5摄像头监控数据自动报告生成工具 ===${NC}"
echo -e "${YELLOW}日期: $DATE${NC}"
echo ""

# 查找CSV文件
CSV_FILE="allure-report/24h-monitoring/$DATE/ssh_monitoring_data.csv"

# 如果指定日期的文件不存在，列出所有可用的CSV文件
if [ ! -f "$CSV_FILE" ]; then
    echo -e "${RED}❌ CSV文件不存在: $CSV_FILE${NC}"
    echo ""
    echo -e "${YELLOW}可用的监控数据文件:${NC}"
    AVAILABLE_CSV=$(find allure-report -name "ssh_monitoring_data.csv" -type f 2>/dev/null | sort)
    if [ -z "$AVAILABLE_CSV" ]; then
        echo "  没有找到任何监控数据文件"
        echo "  请先运行监控测试: ./stability_test.sh"
    else
        echo "$AVAILABLE_CSV" | while read -r csv; do
            # 提取日期
            dir_name=$(dirname "$csv")
            date_part=$(basename "$dir_name")
            if [ -n "$date_part" ]; then
                file_size=$(ls -lh "$csv" 2>/dev/null | awk '{print $5}')
                line_count=$(wc -l < "$csv" 2>/dev/null | tr -d ' ')
                echo -e "  📅 ${GREEN}$date_part${NC} - $csv (大小: $file_size, 行数: $line_count)"
            fi
        done
        echo ""
        echo -e "${YELLOW}使用方法:${NC}"
        echo "  ./auto_generate_reports.sh <日期>  # 例如: ./auto_generate_reports.sh 2025-10-29"
    fi
    exit 1
fi

echo -e "${GREEN}找到CSV文件: $CSV_FILE${NC}"

# 步骤1: 自动修复CSV格式
echo -e "${BLUE}步骤1: 检查并修复CSV格式...${NC}"
if python3 Stability/smart_csv_fixer.py "$CSV_FILE"; then
    echo -e "${GREEN}✅ CSV格式检查完成${NC}"
else
    echo -e "${RED}❌ CSV格式修复失败${NC}"
    exit 1
fi

echo ""

# 步骤2: 生成报告
echo -e "${BLUE}步骤2: 生成监控报告...${NC}"
if python3 Stability/generate_report_from_csv.py "$CSV_FILE"; then
    echo -e "${GREEN}✅ 报告生成成功！${NC}"
else
    echo -e "${RED}❌ 报告生成失败${NC}"
    exit 1
fi

echo ""

# 步骤3: 显示生成的文件
OUTPUT_DIR="allure-report/24h-monitoring/$DATE"
echo -e "${YELLOW}生成的文件:${NC}"
if [ -f "$OUTPUT_DIR/ssh_monitoring_charts.png" ]; then
    echo "📊 监控图表: $OUTPUT_DIR/ssh_monitoring_charts.png"
fi
if [ -f "$OUTPUT_DIR/monitoring_statistics_report.txt" ]; then
    echo "📈 统计报告: $OUTPUT_DIR/monitoring_statistics_report.txt"
fi
if [ -f "$OUTPUT_DIR/monitoring_summary_report.txt" ]; then
    echo "📋 汇总报告: $OUTPUT_DIR/monitoring_summary_report.txt"
fi

echo ""
echo -e "${BLUE}使用方法:${NC}"
echo "  ./auto_generate_reports.sh                    # 生成今天的报告"
echo "  ./auto_generate_reports.sh 2025-10-21         # 生成指定日期的报告"
echo "  ./auto_generate_reports.sh --help             # 显示帮助信息"

# 显示帮助信息
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo ""
    echo -e "${YELLOW}帮助信息:${NC}"
    echo "这个脚本会自动："
    echo "1. 检查CSV文件格式"
    echo "2. 修复任何格式问题"
    echo "3. 生成完整的监控报告"
    echo ""
    echo "支持的文件："
    echo "- 监控图表 (PNG格式)"
    echo "- 统计报告 (TXT格式)"
    echo "- 汇总报告 (TXT格式)"
    echo ""
    echo "如果遇到问题，可以："
    echo "- 检查CSV文件是否存在"
    echo "- 确保Python环境正确"
    echo "- 查看错误日志"
fi
