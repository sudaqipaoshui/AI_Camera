#!/bin/bash

# AI摄像头安全测试运行脚本
# 用于快速运行安全测试套件

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 显示帮助信息
show_help() {
    echo "AI摄像头安全测试运行脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -h, --help              显示帮助信息"
    echo "  -a, --all               运行所有安全测试"
    echo "  -c, --auth              运行认证安全测试"
    echo "  -n, --network           运行网络安全测试"
    echo "  -p, --privacy           运行数据隐私保护测试"
    echo "  -e, --encryption        运行加密验证测试"
    echo "  -r, --access            运行访问控制测试"
    echo "  -t, --target HOST       指定目标主机 (默认: 192.168.2.119)"
    echo "  -o, --output DIR        指定输出目录 (默认: allure-report)"
    echo "  -v, --verbose           启用详细输出"
    echo "  -q, --quiet             静默模式"
    echo "  --no-report             不生成报告"
    echo "  --parallel N            并行运行N个测试 (默认: 4)"
    echo ""
    echo "示例:"
    echo "  $0 --all                                    # 运行所有安全测试"
    echo "  $0 --auth --target 192.168.1.100           # 运行认证测试，指定目标"
    echo "  $0 --network --output /tmp/security-report  # 运行网络测试，指定输出目录"
    echo "  $0 --all --parallel 8 --verbose             # 运行所有测试，8个并行，详细输出"
}

# 默认参数
TARGET_HOST="192.168.2.119"
OUTPUT_DIR="allure-report"
VERBOSE=false
QUIET=false
GENERATE_REPORT=true
PARALLEL_WORKERS=4
TEST_TYPE="all"

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -a|--all)
            TEST_TYPE="all"
            shift
            ;;
        -c|--auth)
            TEST_TYPE="auth"
            shift
            ;;
        -n|--network)
            TEST_TYPE="network"
            shift
            ;;
        -p|--privacy)
            TEST_TYPE="privacy"
            shift
            ;;
        -e|--encryption)
            TEST_TYPE="encryption"
            shift
            ;;
        -r|--access)
            TEST_TYPE="access"
            shift
            ;;
        -t|--target)
            TARGET_HOST="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -q|--quiet)
            QUIET=true
            shift
            ;;
        --no-report)
            GENERATE_REPORT=false
            shift
            ;;
        --parallel)
            PARALLEL_WORKERS="$2"
            shift 2
            ;;
        *)
            log_error "未知参数: $1"
            show_help
            exit 1
            ;;
    esac
done

# 检查Python环境
check_python() {
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 未安装或不在PATH中"
        exit 1
    fi
    
    if ! command -v pytest &> /dev/null; then
        log_error "pytest 未安装，请运行: pip install pytest"
        exit 1
    fi
}

# 检查目标主机连通性
check_target() {
    log_info "检查目标主机连通性: $TARGET_HOST"
    
    if ping -c 1 -W 3 "$TARGET_HOST" &> /dev/null; then
        log_success "目标主机 $TARGET_HOST 可达"
    else
        log_warning "目标主机 $TARGET_HOST 不可达，但测试将继续进行"
    fi
}

# 创建输出目录
create_output_dir() {
    if [ ! -d "$OUTPUT_DIR" ]; then
        log_info "创建输出目录: $OUTPUT_DIR"
        mkdir -p "$OUTPUT_DIR"
    fi
}

# 运行安全测试
run_security_tests() {
    local test_file=""
    local test_name=""
    
    case $TEST_TYPE in
        "all")
            test_file="Security/"
            test_name="所有安全测试"
            ;;
        "auth")
            test_file="Security/test_authentication_security.py"
            test_name="认证安全测试"
            ;;
        "network")
            test_file="Security/test_network_security.py"
            test_name="网络安全测试"
            ;;
        "privacy")
            test_file="Security/test_data_privacy.py"
            test_name="数据隐私保护测试"
            ;;
        "encryption")
            test_file="Security/test_encryption_validation.py"
            test_name="加密验证测试"
            ;;
        "access")
            test_file="Security/test_access_control.py"
            test_name="访问控制测试"
            ;;
    esac
    
    log_info "开始运行 $test_name"
    log_info "目标主机: $TARGET_HOST"
    log_info "输出目录: $OUTPUT_DIR"
    
    # 构建pytest命令
    local pytest_cmd="pytest $test_file"
    
    # 添加参数
    if [ "$VERBOSE" = true ]; then
        pytest_cmd="$pytest_cmd -v -s"
    elif [ "$QUIET" = false ]; then
        pytest_cmd="$pytest_cmd -v"
    fi
    
    # 添加并行参数
    if [ "$PARALLEL_WORKERS" -gt 1 ]; then
        pytest_cmd="$pytest_cmd -n $PARALLEL_WORKERS"
    fi
    
    # 添加Allure报告参数
    if [ "$GENERATE_REPORT" = true ]; then
        pytest_cmd="$pytest_cmd --alluredir $OUTPUT_DIR/allure-results"
    fi
    
    # 设置环境变量
    export TARGET_HOST="$TARGET_HOST"
    
    # 运行测试
    log_info "执行命令: $pytest_cmd"
    
    if eval "$pytest_cmd"; then
        log_success "$test_name 完成"
        return 0
    else
        log_error "$test_name 失败"
        return 1
    fi
}

# 生成报告
generate_report() {
    if [ "$GENERATE_REPORT" = false ]; then
        return 0
    fi
    
    if [ ! -d "$OUTPUT_DIR/allure-results" ]; then
        log_warning "没有找到Allure结果文件，跳过报告生成"
        return 0
    fi
    
    log_info "生成Allure报告"
    
    # 检查allure命令
    if ! command -v allure &> /dev/null; then
        log_warning "Allure 未安装，跳过报告生成"
        log_info "安装Allure: https://docs.qameta.io/allure/#_installing_a_commandline"
        return 0
    fi
    
    # 生成报告
    if allure generate "$OUTPUT_DIR/allure-results" -o "$OUTPUT_DIR/allure-report" --clean; then
        log_success "Allure报告生成成功: $OUTPUT_DIR/allure-report/index.html"
    else
        log_error "Allure报告生成失败"
        return 1
    fi
}

# 显示测试摘要
show_summary() {
    local result_file="$OUTPUT_DIR/allure-results"
    
    if [ -d "$result_file" ]; then
        log_info "测试摘要:"
        
        # 统计测试结果
        local total_tests=$(find "$result_file" -name "*.json" | wc -l)
        local passed_tests=$(find "$result_file" -name "*.json" -exec grep -l '"status":"passed"' {} \; | wc -l)
        local failed_tests=$(find "$result_file" -name "*.json" -exec grep -l '"status":"failed"' {} \; | wc -l)
        
        echo "  总测试数: $total_tests"
        echo "  通过: $passed_tests"
        echo "  失败: $failed_tests"
        
        if [ "$failed_tests" -gt 0 ]; then
            log_warning "发现 $failed_tests 个失败的测试"
        else
            log_success "所有测试通过"
        fi
    fi
}

# 主函数
main() {
    log_info "AI摄像头安全测试套件"
    log_info "===================="
    
    # 检查环境
    check_python
    check_target
    
    # 准备环境
    create_output_dir
    
    # 运行测试
    if run_security_tests; then
        # 生成报告
        generate_report
        show_summary
        log_success "安全测试完成"
        exit 0
    else
        log_error "安全测试失败"
        exit 1
    fi
}

# 运行主函数
main "$@"


