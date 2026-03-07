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

# 全局变量（用户输入的配置）
API_KEY=""
BASE_URL=""
MODEL=""

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
        Linux*)     OS=Linux;;
        Darwin*)    OS=Mac;;
        CYGWIN*)    OS=Cygwin;;
        MINGW*)     OS=MinGw;;
        *)          OS="UNKNOWN"
    esac
    info "检测到操作系统: $OS"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" &> /dev/null
}

# 检查 Python 版本
check_python() {
    info "检查 Python 版本..."

    PYTHON_CMD=""
    MIN_PYTHON_MAJOR=3
    MIN_PYTHON_MINOR=10

    # 检查 python3
    if command_exists python3; then
        PYTHON_CMD=python3
    elif command_exists python; then
        PYTHON_CMD=python
    else
        error "未找到 Python。请安装 Python 3.10 或更高版本。"
    fi

    # 获取版本
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
    PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)

    info "找到 Python 版本: $PYTHON_VERSION"

    if [ "$PYTHON_MAJOR" -lt "$MIN_PYTHON_MAJOR" ] || \
       [ "$PYTHON_MAJOR" -eq "$MIN_PYTHON_MAJOR" -a "$PYTHON_MINOR" -lt "$MIN_PYTHON_MINOR" ]; then
        error "Python 版本过低。需要 Python $MIN_PYTHON_MAJOR.$MIN_PYTHON_MINOR 或更高版本，当前版本: $PYTHON_VERSION"
    fi

    success "Python 版本检查通过"
}

# 检查 Node.js 版本
check_nodejs() {
    info "检查 Node.js 版本..."

    if ! command_exists node; then
        warn "未找到 Node.js。MCP 功能需要 Node.js 18+。"
        warn "请访问 https://nodejs.org 安装 Node.js"
        warn "你可以继续安装，但 MCP 功能将无法使用。"
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

# 检查 Git
check_git() {
    info "检查 Git..."

    if ! command_exists git; then
        error "未找到 Git。请先安装 Git。"
    fi

    success "Git 检查通过"
}

# 克隆仓库
clone_repo() {
    REPO_URL="git@github.com:shenh1995/my-agent.git"
    INSTALL_DIR="${INSTALL_DIR:-$HOME/my-agent}"

    info "安装目录: $INSTALL_DIR"

    if [ -d "$INSTALL_DIR" ]; then
        warn "目录 $INSTALL_DIR 已存在"
        if prompt_confirm "是否删除并重新安装? (y/N): "; then
            info "删除现有目录..."
            rm -rf "$INSTALL_DIR"
        else
            error "安装已取消"
        fi
    fi

    info "克隆仓库..."
    git clone "$REPO_URL" "$INSTALL_DIR"

    cd "$INSTALL_DIR"

    # 给脚本添加执行权限
    chmod +x install.sh

    success "仓库克隆完成"
}

# 创建虚拟环境
create_venv() {
    info "创建虚拟环境..."

    $PYTHON_CMD -m venv .venv

    # 激活虚拟环境
    if [ "$OS" = "Mac" ] || [ "$OS" = "Linux" ]; then
        source .venv/bin/activate
    else
        source .venv/Scripts/activate
    fi

    success "虚拟环境创建完成并已激活"
}

# 安装依赖
install_dependencies() {
    info "安装 Python 依赖..."

    pip install --upgrade pip
    pip install -e .

    success "依赖安装完成"
}

# 配置环境变量
setup_env() {
    info "配置环境变量..."

    if [ ! -f ".env" ]; then
        echo ""
        echo -e "${YELLOW}请输入以下配置信息（直接回车使用默认值）:${NC}"
        echo ""

        # 获取 ANTHROPIC_API_KEY
        echo -e "${BLUE}ANTHROPIC_API_KEY (必填):${NC}"
        prompt_input "  请输入你的 API Key: " API_KEY
        while [ -z "$API_KEY" ]; do
            echo -e "${RED}  API Key 不能为空，请重新输入${NC}"
            prompt_input "  请输入你的 API Key: " API_KEY
        done

        # 获取 ANTHROPIC_BASE_URL
        echo ""
        echo -e "${BLUE}ANTHROPIC_BASE_URL (可选，直接回车跳过):${NC}"
        prompt_input "  请输入 API Base URL: " BASE_URL

        # 获取 ANTHROPIC_MODEL
        echo ""
        echo -e "${BLUE}ANTHROPIC_MODEL (可选，默认: claude-sonnet-4-6):${NC}"
        prompt_input "  请输入模型名称: " MODEL "claude-sonnet-4-6"

        # 创建 .env 文件
        echo ""
        info "正在创建 .env 文件..."

        cat > .env << EOF
# Anthropic API 配置
# 必填：你的 Anthropic API Key
ANTHROPIC_API_KEY=${API_KEY}
EOF

        # 添加可选配置
        if [ -n "$BASE_URL" ]; then
            echo "" >> .env
            echo "# API 基础 URL" >> .env
            echo "ANTHROPIC_BASE_URL=${BASE_URL}" >> .env
        fi

        if [ -n "$MODEL" ]; then
            echo "" >> .env
            echo "# 模型选择" >> .env
            echo "ANTHROPIC_MODEL=${MODEL}" >> .env
        fi

        success ".env 文件创建完成"
    else
        info ".env 文件已存在，跳过"
    fi
}

# 配置 Claude Code settings
setup_claude_settings() {
    info "配置 Claude Code settings..."

    CLAUDE_DIR="$HOME/.claude"
    SETTINGS_FILE="$CLAUDE_DIR/settings.json"

    # 创建 .claude 目录
    if [ ! -d "$CLAUDE_DIR" ]; then
        mkdir -p "$CLAUDE_DIR"
        info "已创建目录: $CLAUDE_DIR"
    fi

    # 如果 settings.json 已存在，询问是否覆盖
    if [ -f "$SETTINGS_FILE" ]; then
        warn "settings.json 已存在"
        if ! prompt_confirm "是否覆盖? (y/N): "; then
            info "跳过 settings.json 配置"
            return
        fi
    fi

    # 创建 settings.json（使用用户输入的值）
    cat > "$SETTINGS_FILE" << EOF
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "${API_KEY}",
    "ANTHROPIC_BASE_URL": "${BASE_URL}",
    "ANTHROPIC_MODEL": "${MODEL}",
    "API_TIMEOUT_MS": "3000000",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1"
  }
}
EOF

    success "settings.json 创建完成: $SETTINGS_FILE"
}

# 打印安装完成信息
print_success_message() {
    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}         安装完成！${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo "安装目录: $INSTALL_DIR"
    echo ""
    echo "后续步骤:"
    echo ""
    echo "  1. 进入项目目录:"
    echo "     cd $INSTALL_DIR"
    echo ""
    echo "  2. 激活虚拟环境:"
    if [ "$OS" = "Mac" ] || [ "$OS" = "Linux" ]; then
        echo "     source .venv/bin/activate"
    else
        echo "     .venv\\Scripts\\activate"
    fi
    echo ""
    echo "  3. 运行程序:"
    echo "     my_claude"
    echo ""
    if [ "$OS" = "Mac" ]; then
        echo "  提示: 你可以将以下内容添加到 ~/.zshrc 以便快速启动:"
        echo "     alias my_claude='cd $INSTALL_DIR && source .venv/bin/activate && my_claude'"
    elif [ "$OS" = "Linux" ]; then
        echo "  提示: 你可以将以下内容添加到 ~/.bashrc 以便快速启动:"
        echo "     alias my_claude='cd $INSTALL_DIR && source .venv/bin/activate && my_claude'"
    fi
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
    check_git
    check_python
    check_nodejs
    clone_repo
    create_venv
    install_dependencies
    setup_env
    setup_claude_settings
    print_success_message
}

# 运行主函数
main "$@"