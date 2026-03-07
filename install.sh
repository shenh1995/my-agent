#!/bin/bash

# My Agent 安装脚本
# 使用方法: curl -fsSL https://cdn.jsdelivr.net/gh/shenh1995/my-agent@main/install.sh | bash

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# GitHub 仓库信息
REPO_OWNER="shenh1995"
REPO_NAME="my-agent"
RELEASES_URL="https://github.com/${REPO_OWNER}/${REPO_NAME}/releases"

# 从终端读取输入（解决管道执行问题）
prompt_input() {
    local prompt_msg="$1"
    local var_name="$2"
    local default_val="${3:-}"
    local input_val

    if [ -t 0 ]; then
        # 直接在终端运行
        read -p "$prompt_msg" input_val
    else
        # 管道执行，从 /dev/tty 读取
        echo -n "$prompt_msg" > /dev/tty
        read input_val < /dev/tty
    fi

    # 如果输入为空，使用默认值
    if [ -z "$input_val" ] && [ -n "$default_val" ]; then
        input_val="$default_val"
    fi

    eval "$var_name=\"\$input_val\""
}

# 确认输入（y/N）
prompt_confirm() {
    local prompt_msg="$1"
    local reply

    if [ -t 0 ]; then
        read -p "$prompt_msg" -n 1 -r reply
        echo
    else
        echo -n "$prompt_msg" > /dev/tty
        read -n 1 -r reply < /dev/tty
        echo > /dev/tty
    fi

    [[ $reply =~ ^[Yy]$ ]]
}

# 打印函数
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# 检测操作系统
detect_os() {
    case "$(uname -s)" in
        Linux*)     OS=linux;;
        Darwin*)    OS=macos;;
        CYGWIN*)    OS=windows;;
        MINGW*)     OS=windows;;
        *)          error "不支持的操作系统: $(uname -s)";;
    esac
    info "检测到操作系统: $OS"
}

# 检测架构
detect_arch() {
    case "$(uname -m)" in
        x86_64|amd64)   ARCH=x86_64;;
        arm64|aarch64)  ARCH=arm64;;
        *)              error "不支持的架构: $(uname -m)";;
    esac
    info "检测到架构: $ARCH"
}

# 获取最新版本号
get_latest_version() {
    info "获取最新版本..."

    LATEST_VERSION=$(wget -qO- "https://api.github.com/repos/${REPO_OWNER}/${REPO_NAME}/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')

    if [ -z "$LATEST_VERSION" ]; then
        error "无法获取最新版本信息"
    fi

    info "最新版本: $LATEST_VERSION"
}

# 构建下载文件名
get_download_filename() {
    if [ "$OS" = "windows" ]; then
        echo "my_claude-windows-x86_64.exe"
    elif [ "$OS" = "macos" ] && [ "$ARCH" = "arm64" ]; then
        echo "my_claude-macos-arm64"
    elif [ "$OS" = "macos" ] && [ "$ARCH" = "x86_64" ]; then
        echo "my_claude-macos-x86_64"
    else
        echo "my_claude-${OS}-${ARCH}"
    fi
}

# 下载二进制文件
download_binary() {

    info "downloading binary..."
    FILENAME=$(get_download_filename)
    info "FILENAME: $FILENAME"
    DOWNLOAD_URL="https://gh-proxy.com/${RELEASES_URL}/download/${LATEST_VERSION}/${FILENAME}"

    info "下载地址: $DOWNLOAD_URL"

    # 临时文件
    TEMP_DIR=$(mktemp -d)
    TEMP_FILE="${TEMP_DIR}/${FILENAME}"

    # 下载文件
    if ! wget -q "$DOWNLOAD_URL" -O "$TEMP_FILE"; then
        error "下载失败。请检查网络连接或版本是否存在。"
    fi

    # 检查文件是否下载成功
    if [ ! -f "$TEMP_FILE" ] || [ ! -s "$TEMP_FILE" ]; then
        error "下载的文件无效"
    fi

    chmod +x "$TEMP_FILE"

    echo "$TEMP_FILE"
}

# 安装二进制文件
install_binary() {
    TEMP_FILE="$1"
    INSTALL_DIR="/usr/local/bin"

    info "安装目录: $INSTALL_DIR"

    # 检查是否有写入权限
    if [ ! -w "$INSTALL_DIR" ]; then
        warn "需要管理员权限安装到 $INSTALL_DIR"
        if command -v sudo &> /dev/null; then
            sudo mv "$TEMP_FILE" "${INSTALL_DIR}/my_claude"
            sudo chmod +x "${INSTALL_DIR}/my_claude"
        else
            error "无法获取管理员权限"
        fi
    else
        mv "$TEMP_FILE" "${INSTALL_DIR}/my_claude"
        chmod +x "${INSTALL_DIR}/my_claude"
    fi

    success "二进制文件已安装到 ${INSTALL_DIR}/my_claude"

    # 清理临时目录
    rm -rf "$(dirname "$TEMP_FILE")"
}

# 检查 Node.js 版本（可选）
check_nodejs() {
    info "检查 Node.js..."

    if ! command -v node &> /dev/null; then
        warn "未找到 Node.js。MCP 功能需要 Node.js 18+。"
        warn "请访问 https://nodejs.org 安装 Node.js"
        warn "你可以继续使用，但 MCP 功能将无法使用。"
        return
    fi

    NODE_VERSION=$(node --version | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VERSION" | cut -d. -f1)

    info "找到 Node.js 版本: $NODE_VERSION"

    if [ "$NODE_MAJOR" -lt 18 ]; then
        warn "Node.js 版本过低。MCP 功能需要 Node.js 18+，当前版本: $NODE_VERSION"
        warn "MCP 功能可能无法正常工作。"
    else
        success "Node.js 版本检查通过"
    fi
}

# 打印安装完成信息
print_success_message() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}         安装完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "安装版本: $LATEST_VERSION"
    echo "安装位置: /usr/local/bin/my_claude"
    echo ""
    echo "运行程序:"
    echo "  my_claude"
    echo ""
    echo "首次运行将引导你配置 API Key、Base URL 和模型。"
    echo ""
}

# 主安装流程
main() {
    echo -e "${BLUE}"
    echo "========================================"
    echo "      My Agent 安装脚本"
    echo "========================================"
    echo -e "${NC}"

    detect_os
    detect_arch
    get_latest_version
    check_nodejs

    info "开始下载二进制文件..."
    info "downloading binary..."
    FILENAME=$(get_download_filename)
    info "FILENAME: $FILENAME"
    DOWNLOAD_URL="https://gh-proxy.com/${RELEASES_URL}/download/${LATEST_VERSION}/${FILENAME}"

    info "下载地址: $DOWNLOAD_URL"

    # 临时文件
    TEMP_DIR=$(mktemp -d)
    TEMP_FILE="${TEMP_DIR}/${FILENAME}"

    # 下载文件
    if ! wget -q "$DOWNLOAD_URL" -O "$TEMP_FILE"; then
        error "下载失败。请检查网络连接或版本是否存在。"
    fi

    # 检查文件是否下载成功
    if [ ! -f "$TEMP_FILE" ] || [ ! -s "$TEMP_FILE" ]; then
        error "下载的文件无效"
    fi

    chmod +x "$TEMP_FILE"

    info "安装二进制文件..."
    install_binary "$TEMP_FILE"

    print_success_message
}

# 运行主函数
main "$@"