#!/bin/bash
# 基准测试报告快速清理脚本

cd "$(dirname "$0")/.."

echo "============================================================"
echo "基准测试报告清理工具"
echo "============================================================"

# 检查清理脚本是否存在
CLEANUP_SCRIPT="Benchmark/cleanup_benchmark_reports.py"
if [ ! -f "$CLEANUP_SCRIPT" ]; then
    echo "错误: 清理脚本不存在: $CLEANUP_SCRIPT"
    exit 1
fi

# 解析命令行参数
ACTION="${1:-list}"

case "$ACTION" in
    list|ls)
        echo "列出所有报告..."
        python3 "$CLEANUP_SCRIPT" list
        ;;
    list-detail|ls-d)
        echo "详细列出所有报告..."
        python3 "$CLEANUP_SCRIPT" list -d
        ;;
    clean|empty)
        if [ "$2" == "delete" ] || [ "$2" == "--delete" ]; then
            echo "删除空报告目录..."
            python3 "$CLEANUP_SCRIPT" clean --delete
        else
            echo "预览空报告目录..."
            python3 "$CLEANUP_SCRIPT" clean
            echo ""
            echo "要实际删除，请运行: $0 clean delete"
        fi
        ;;
    old)
        DAYS="${2:-7}"
        if [ "$3" == "delete" ] || [ "$3" == "--delete" ]; then
            echo "删除 $DAYS 天前的旧报告..."
            python3 "$CLEANUP_SCRIPT" old --delete --days=$DAYS
        else
            echo "预览 $DAYS 天前的旧报告..."
            python3 "$CLEANUP_SCRIPT" old --days=$DAYS
            echo ""
            echo "要实际删除，请运行: $0 old $DAYS delete"
        fi
        ;;
    help|--help|-h)
        echo "用法: $0 [命令] [选项]"
        echo ""
        echo "命令:"
        echo "  list              - 列出所有报告"
        echo "  list-detail        - 详细列出所有报告"
        echo "  clean              - 预览空报告目录"
        echo "  clean delete       - 删除空报告目录"
        echo "  old [天数]         - 预览旧报告（默认7天）"
        echo "  old [天数] delete  - 删除旧报告（默认7天）"
        echo ""
        echo "示例:"
        echo "  $0 list                    # 列出所有报告"
        echo "  $0 clean                  # 预览空报告"
        echo "  $0 clean delete           # 删除空报告"
        echo "  $0 old 3                  # 预览3天前的报告"
        echo "  $0 old 7 delete           # 删除7天前的报告"
        ;;
    *)
        echo "未知命令: $ACTION"
        echo "使用 '$0 help' 查看帮助"
        exit 1
        ;;
esac

