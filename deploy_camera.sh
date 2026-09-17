#!/bin/bash
# AI摄像头Deploy安装包部署脚本
# 功能：自动下载、部署、安装最新的deploy包到摄像头

set -e  # 遇到错误时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 载入项目根 .env 里的凭据(该文件不入库)。
# 真实环境变量优先: .env 里的同名变量不会覆盖已存在的环境变量。
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"
if [ -f "$ENV_FILE" ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        # 跳过空行与注释
        case "$line" in ''|'#'*) continue ;; esac
        # 允许 export 前缀
        line="${line#export }"
        key="${line%%=*}"
        value="${line#*=}"
        # 去掉键两端空白
        key="$(printf '%s' "$key" | tr -d '[:space:]')"
        [ -z "$key" ] && continue
        # 去掉值两端成对引号
        case "$value" in
            \"*\") value="${value#\"}"; value="${value%\"}" ;;
            \'*\') value="${value#\'}"; value="${value%\'}" ;;
        esac
        # 已存在的环境变量优先, 不覆盖
        if [ -z "${!key:-}" ]; then
            export "$key=$value"
        fi
    done < "$ENV_FILE"
fi

# 默认配置
DEFAULT_DEPLOY_URL="https://pic.dream-sports.cn/console/apk-file/2026/01/07/2c7a58e0cf1041e5afce02aef06637e6.rm"
DEFAULT_CAMERA_IPS=("192.168.2.30")
DEFAULT_SSH_USER="root"
# 不再写死默认口令, 统一取 .env / 环境变量
DEFAULT_SSH_PASS="${CAMERA_SSH_PASSWORD:-}"
DEFAULT_DEPLOY_DIR="/userdata/deploy"

# 临时目录
TEMP_DIR=".version/camera_deploy_$(date +%s)"
DEPLOY_PACKAGE="deploy.tar.gz"

# 显示使用帮助
show_help() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}AI摄像头Deploy部署脚本${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
    echo "用法:"
    echo "  $0 [选项]"
    echo ""
    echo "选项:"
    echo "  -u, --url URL              Deploy安装包下载URL"
    echo "  -i, --ip IP1,IP2,...       摄像头IP地址（多个用逗号分隔）"
    echo "  -U, --user USERNAME        SSH用户名（默认：root）"
    echo "  -P, --password PASSWORD    SSH密码（默认取 .env 的 CAMERA_SSH_PASSWORD）"
    echo "  -d, --deploy-dir DIR       Deploy目录（默认：/userdata/deploy）"
    echo "  -n, --no-reboot            部署后不重启摄像头"
    echo "  -y, --yes                  跳过确认提示，自动开始部署"
    echo "  -h, --help                 显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  # 部署到单个摄像头"
    echo "  $0 -u https://pic-dev.dream-sports.cn/console/apk-file/2025/12/25/4f761f6818b24b388c417b03592d03eb.rm -i 192.168.2.30"
    echo ""
    echo "  # 部署到多个摄像头"
    echo "  $0 -u https://pic-dev.dream-sports.cn/console/apk-file/2025/12/25/4f761f6818b24b388c417b03592d03eb.rm -i 192.168.3.28,192.168.3.29,192.168.3.30"
    echo ""
    echo "  # 部署后不重启"
    echo "  $0 -u https://pic-dev.dream-sports.cn/console/apk-file/2025/12/25/4f761f6818b24b388c417b03592d03eb.rm -i 192.168.3.29 -n"
    echo ""
}

# 解析命令行参数
DEPLOY_URL="$DEFAULT_DEPLOY_URL"
CAMERA_IPS_STR=""
SSH_USER="$DEFAULT_SSH_USER"
SSH_PASS="$DEFAULT_SSH_PASS"
DEPLOY_DIR="$DEFAULT_DEPLOY_DIR"
NO_REBOOT=false
AUTO_YES=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--url)
            DEPLOY_URL="$2"
            shift 2
            ;;
        -i|--ip)
            CAMERA_IPS_STR="$2"
            shift 2
            ;;
        -U|--user)
            SSH_USER="$2"
            shift 2
            ;;
        -P|--password)
            SSH_PASS="$2"
            shift 2
            ;;
        -d|--deploy-dir)
            DEPLOY_DIR="$2"
            shift 2
            ;;
        -n|--no-reboot)
            NO_REBOOT=true
            shift
            ;;
        -y|--yes)
            AUTO_YES=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo -e "${RED}错误: 未知参数 $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# 解析摄像头IP列表
if [ -n "$CAMERA_IPS_STR" ]; then
    IFS=',' read -ra CAMERA_IPS <<< "$CAMERA_IPS_STR"
else
    CAMERA_IPS=("${DEFAULT_CAMERA_IPS[@]}")
fi

# 口令校验: 既不再内置默认口令, 也不允许空口令继续往下走
if [ -z "$SSH_PASS" ]; then
    echo -e "${RED}错误: 未提供 SSH 密码${NC}"
    echo "  请任选其一:"
    echo "    1) 在项目根 .env 里设置 CAMERA_SSH_PASSWORD=<真实口令>"
    echo "    2) 用 -P/--password 显式传入"
    echo "    3) 导出环境变量 CAMERA_SSH_PASSWORD"
    exit 1
fi

# 检查依赖
check_dependencies() {
    echo -e "${BLUE}检查依赖工具...${NC}"
    
    # 检查 sshpass
    if ! command -v sshpass &> /dev/null; then
        echo -e "${YELLOW}警告: 未安装 sshpass${NC}"
        echo "安装方法："
        echo "  macOS: brew install sshpass"
        echo "  Ubuntu/Debian: sudo apt-get install sshpass"
        echo "  CentOS/RHEL: sudo yum install sshpass"
        return 1
    fi
    
    # 检查 wget 或 curl
    if ! command -v wget &> /dev/null && ! command -v curl &> /dev/null; then
        echo -e "${RED}错误: 需要 wget 或 curl 来下载文件${NC}"
        return 1
    fi
    
    echo -e "${GREEN}✓ 依赖检查通过${NC}"
    return 0
}

# 创建临时目录
create_temp_dir() {
    echo -e "${BLUE}创建临时目录...${NC}"
    mkdir -p "$TEMP_DIR"
    echo -e "${GREEN}✓ 临时目录: $TEMP_DIR${NC}"
}

# 下载Deploy安装包
download_deploy_package() {
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}步骤 1/5: 下载Deploy安装包${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo -e "URL: ${YELLOW}$DEPLOY_URL${NC}"
    
    local download_path="$TEMP_DIR/$DEPLOY_PACKAGE"
    
    # 使用 wget 或 curl 下载
    if command -v wget &> /dev/null; then
        echo "使用 wget 下载..."
        if wget -O "$download_path" "$DEPLOY_URL" 2>&1 | grep --line-buffered "%" | sed -u 's/.*\([0-9]\+%\).*/\1/'; then
            echo -e "${GREEN}✓ 下载完成${NC}"
        else
            echo -e "${RED}✗ 下载失败${NC}"
            return 1
        fi
    elif command -v curl &> /dev/null; then
        echo "使用 curl 下载..."
        if curl -L -o "$download_path" --progress-bar "$DEPLOY_URL"; then
            echo -e "${GREEN}✓ 下载完成${NC}"
        else
            echo -e "${RED}✗ 下载失败${NC}"
            return 1
        fi
    fi
    
    # 检查文件是否下载成功
    if [ ! -f "$download_path" ]; then
        echo -e "${RED}✗ 下载的文件不存在${NC}"
        return 1
    fi
    
    # 显示文件大小
    local file_size=$(du -h "$download_path" | cut -f1)
    echo -e "文件大小: ${GREEN}$file_size${NC}"
    
    return 0
}

# 部署到单个摄像头
deploy_to_camera() {
    local camera_ip=$1
    
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}部署到摄像头: $camera_ip${NC}"
    echo -e "${BLUE}================================================${NC}"
    
    # 步骤 2: SSH连接测试
    echo -e "${BLUE}步骤 2/5: 测试SSH连接...${NC}"
    echo "调试信息: SSH_USER=$SSH_USER, camera_ip=$camera_ip"
    
    # 测试SSH连接
    ssh_test_output=$(sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 \
        ${SSH_USER}@${camera_ip} "echo 'SSH连接成功'" 2>&1)
    ssh_test_result=$?
    
    if [ $ssh_test_result -ne 0 ]; then
        echo -e "${RED}✗ SSH连接失败: $camera_ip${NC}"
        echo "错误信息: $ssh_test_output"
        return 1
    fi
    echo -e "${GREEN}✓ SSH连接成功${NC}"
    
    # 步骤 3: 备份并删除旧的deploy目录
    echo -e "${BLUE}步骤 3/5: 删除旧的deploy目录...${NC}"
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${camera_ip} \
        "if [ -d '$DEPLOY_DIR' ]; then \
            echo '备份旧版本...'; \
            rm -rf ${DEPLOY_DIR}.backup 2>/dev/null || true; \
            mv $DEPLOY_DIR ${DEPLOY_DIR}.backup 2>/dev/null || true; \
            echo '删除旧目录...'; \
            rm -rf $DEPLOY_DIR; \
        fi; \
        mkdir -p $DEPLOY_DIR" 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 旧目录已清理${NC}"
    else
        echo -e "${RED}✗ 清理失败${NC}"
        return 1
    fi
    
    # 步骤 4: 上传并在摄像头上解压新的deploy包
    echo -e "${BLUE}步骤 4/5: 上传安装包到摄像头...${NC}"
    
    # 上传压缩包到摄像头
    echo "上传安装包（压缩包）到摄像头..."
    if ! sshpass -p "$SSH_PASS" scp -o StrictHostKeyChecking=no \
        "$TEMP_DIR/$DEPLOY_PACKAGE" ${SSH_USER}@${camera_ip}:/userdata/$DEPLOY_PACKAGE 2>&1; then
        echo -e "${RED}✗ 上传失败${NC}"
        return 1
    fi
    echo -e "${GREEN}✓ 上传完成${NC}"
    
    # 在摄像头上解压文件
    echo "在摄像头上解压安装包到 /userdata/ 目录..."
    sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${camera_ip} \
        "echo '开始解压...' && \
         tar -xzf /userdata/$DEPLOY_PACKAGE -C /userdata && \
         echo '解压完成' && \
         echo '清理临时文件...' && \
         rm -f /userdata/$DEPLOY_PACKAGE && \
         echo '设置权限...' && \
         chmod -R 755 $DEPLOY_DIR 2>/dev/null || true && \
         echo '安装完成'" 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ 在摄像头上解压安装完成${NC}"
    else
        echo -e "${RED}✗ 解压安装失败${NC}"
        echo -e "${YELLOW}尝试清理临时文件...${NC}"
        sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${camera_ip} \
            "rm -f /userdata/$DEPLOY_PACKAGE" 2>/dev/null || true
        return 1
    fi
    
    # 步骤 5: 重启摄像头
    if [ "$NO_REBOOT" = false ]; then
        echo -e "${BLUE}步骤 5/5: 重启摄像头...${NC}"
        sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no ${SSH_USER}@${camera_ip} \
            "sync && reboot" 2>&1 &
        echo -e "${GREEN}✓ 重启命令已发送${NC}"
        echo -e "${YELLOW}摄像头正在重启，请等待约30-60秒...${NC}"
    else
        echo -e "${BLUE}步骤 5/5: 跳过重启${NC}"
        echo -e "${YELLOW}注意: 需要手动重启摄像头才能使新版本生效${NC}"
    fi
    
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}✓ 摄像头 $camera_ip 部署完成！${NC}"
    echo -e "${GREEN}================================================${NC}"
    
    return 0
}

# 清理临时文件
cleanup() {
    echo ""
    echo -e "${BLUE}清理临时文件...${NC}"
    if [ -d "$TEMP_DIR" ]; then
        rm -rf "$TEMP_DIR"
        echo -e "${GREEN}✓ 临时文件已清理${NC}"
    fi
}

# 主流程
main() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}AI摄像头Deploy部署脚本${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
    echo "配置信息:"
    echo "  Deploy URL: $DEPLOY_URL"
    echo "  摄像头IP: ${CAMERA_IPS[*]}"
    echo "  SSH用户: $SSH_USER"
    echo "  Deploy目录: $DEPLOY_DIR"
    echo "  部署后重启: $([ "$NO_REBOOT" = true ] && echo "否" || echo "是")"
    echo ""
    
    # 确认
    if [ "$AUTO_YES" != true ]; then
        read -p "确认开始部署? (y/n): " confirm
        if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
            echo "已取消"
            exit 0
        fi
    else
        echo "自动确认模式，开始部署..."
    fi
    
    # 检查依赖
    if ! check_dependencies; then
        exit 1
    fi
    
    # 创建临时目录
    create_temp_dir
    
    # 下载Deploy包
    if ! download_deploy_package; then
        cleanup
        exit 1
    fi
    
    # 部署到所有摄像头
    success_count=0
    fail_count=0
    total_cameras=${#CAMERA_IPS[@]}
    current_index=0
    
    for camera_ip in "${CAMERA_IPS[@]}"; do
        ((current_index++))
        
        if deploy_to_camera "$camera_ip"; then
            ((success_count++))
        else
            ((fail_count++))
            echo -e "${RED}摄像头 $camera_ip 部署失败${NC}"
        fi
        
        # 如果不是最后一个摄像头，等待一下
        if [ $current_index -lt $total_cameras ]; then
            echo ""
            sleep 2
        fi
    done
    
    # 清理
    cleanup
    
    # 显示总结
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}部署总结${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo -e "总计: ${#CAMERA_IPS[@]} 个摄像头"
    echo -e "成功: ${GREEN}$success_count${NC} 个"
    echo -e "失败: ${RED}$fail_count${NC} 个"
    echo ""
    
    if [ $fail_count -eq 0 ]; then
        echo -e "${GREEN}✓ 所有摄像头部署成功！${NC}"
        exit 0
    else
        echo -e "${YELLOW}部分摄像头部署失败，请检查错误信息${NC}"
        exit 1
    fi
}

# 捕获退出信号，确保清理
trap cleanup EXIT INT TERM

# 运行主流程
main

