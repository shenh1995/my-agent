# My Agent

一个基于 [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) 的交互式命令行工具，提供强大的 AI 助手功能。

## 特性

- **交互式 CLI** - 美观的命令行界面，支持多行输入和语法高亮
- **一键安装** - 自动下载预编译二进制文件，无需配置 Python 环境
- **首次运行向导** - 交互式配置 API Key、Base URL 和模型
- **MCP 支持** - 支持 Model Context Protocol，可扩展工具能力
- **Skill 系统** - 通过斜杠命令执行预定义任务
- **Plan Mode** - 只读探索模式，生成计划供审批后执行
- **图片分析** - 支持图片输入和分析
- **检查点管理** - 支持对话历史回溯
- **Bash 集成** - 直接在对话中执行 shell 命令

## 环境要求

- Node.js >= 18 (可选，用于 MCP 服务器)

## 安装

### 一键安装

使用 curl 执行安装脚本：

```bash
curl -fsSL https://cdn.jsdelivr.net/gh/shenh1995/my-agent@main/install.sh | bash
```

或使用 wget：

```bash
wget -qO- https://cdn.jsdelivr.net/gh/shenh1995/my-agent@main/install.sh | bash
```

安装脚本会：
1. 自动检测操作系统和架构
2. 从 GitHub Releases 下载对应的预编译二进制文件
3. 安装到 `/usr/local/bin/my_claude`

## 使用

启动交互式 CLI：

```bash
my_claude
```

### 首次运行

首次运行时，会启动配置向导，引导你输入：

- **API Key** - 你的 API 密钥
- **Base URL** - API 服务地址
- **模型名称** - 使用的模型

配置会保存到 `~/.claude/my-agent/.env` 文件中。

### 修改配置

如需修改配置，编辑配置文件：

```bash
# macOS / Linux
nano ~/.claude/my-agent/.env

# 或直接删除重新配置
rm ~/.claude/my-agent/.env
my_claude  # 会重新启动配置向导
```

### 基本命令

| 命令 | 说明 |
|------|------|
| `quit`, `exit`, `q` | 退出程序 |
| `clear` | 清空屏幕 |
| `help` | 显示帮助信息 |
| `version` | 显示版本信息 |
| `!<command>` | 执行 bash 命令 (例: `!ls -la`) |

### 斜杠命令

| 命令 | 说明 |
|------|------|
| `/clear` | 清除对话历史，开始新对话 |
| `/compact` | 压缩对话历史，保留重要上下文 |
| `/rewind` | 回溯到之前的检查点 |
| `/<skill>` | 执行自定义 Skill |

### 快捷键

| 快捷键 | 说明 |
|--------|------|
| `Enter` | 发送消息 |
| `Ctrl+J` | 换行（多行输入） |
| `Shift+Tab` | 切换 Plan Mode |

### Plan Mode

Plan Mode 是一个只读探索模式：

- Agent 使用只读工具探索代码库
- 生成实施计划供你审批
- 批准后才会执行实际操作

按 `Shift+Tab` 进入或退出 Plan Mode。

### Skills 配置

在 `~/.claude/skills.yaml` 中配置自定义 Skills：

```yaml
skills:
  - name: review
    description: 代码审查
    prompt: |
      请对以下代码进行审查，关注：
      1. 代码质量
      2. 潜在问题
      3. 改进建议

  - name: test
    description: 生成测试
    prompt: 为选中的代码生成单元测试
    tools:
      - write_file
    model: claude-sonnet-4-6
```

使用方式：`/review` 或 `/test`

## 项目结构

```
my-agent/
├── src/
│   └── my_agent/
│       ├── cli.py           # 主入口
│       ├── ui.py            # UI 显示
│       ├── input.py         # 输入处理
│       ├── commands.py      # 命令处理
│       ├── permissions.py   # 权限管理
│       ├── image.py         # 图片分析
│       ├── plan_mode.py     # Plan Mode
│       ├── task_manager.py  # 任务管理
│       ├── highlight.py     # 语法高亮
│       ├── setup_wizard.py  # 首次运行配置向导
│       ├── mcp/             # MCP 支持
│       │   ├── config.py
│       │   ├── server.py
│       │   └── tools/
│       └── skills/          # Skill 系统
│           ├── config.py
│           └── manager.py
├── .github/
│   └── workflows/
│       └── release.yml      # GitHub Actions 自动发布
├── build.spec               # PyInstaller 构建配置
├── run.py                   # PyInstaller 入口
├── install.sh               # 安装脚本
├── pyproject.toml
└── README.md
```

## 从源码构建

如果你需要从源码构建：

```bash
# 克隆仓库
git clone https://github.com/shenh1995/my-agent.git
cd my-agent

# 安装依赖
pip install -e ".[build]"

# 构建二进制文件
pyinstaller build.spec

# 构建产物位于 dist/ 目录
```

## 许可证

MIT License

## 致谢

- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)
- [Model Context Protocol](https://modelcontextprotocol.io/)