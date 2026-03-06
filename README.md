# My Agent

一个基于 [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) 的交互式命令行工具，提供强大的 AI 助手功能。

## 特性

- **交互式 CLI** - 美观的命令行界面，支持多行输入和语法高亮
- **MCP 支持** - 支持 Model Context Protocol，可扩展工具能力
- **Skill 系统** - 通过斜杠命令执行预定义任务
- **Plan Mode** - 只读探索模式，生成计划供审批后执行
- **图片分析** - 支持图片输入和分析
- **检查点管理** - 支持对话历史回溯
- **Bash 集成** - 直接在对话中执行 shell 命令

## 环境要求

- Python >= 3.10
- Node.js >= 18 (用于 MCP 服务器)

## 安装

### 方式一：一键安装（推荐）

使用 curl 执行安装脚本：

```bash
curl -fsSL https://raw.githubusercontent.com/shenh1995/my-agent/main/install.sh | bash
```

或使用 wget：

```bash
wget -qO- https://raw.githubusercontent.com/shenh1995/my-agent/main/install.sh | bash
```

安装完成后，按照提示配置 API 密钥即可使用。

### 方式二：手动安装

#### 1. 克隆仓库

```bash
git clone git@github.com:shenh1995/my-agent.git
cd my-agent
```

#### 2. 创建虚拟环境

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# 或
.venv\Scripts\activate  # Windows
```

#### 3. 安装依赖

```bash
pip install -e .
```

#### 4. 配置环境变量

复制示例配置文件并填入你的 API 密钥：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_API_KEY=your-api-key-here
ANTHROPIC_MODEL=claude-sonnet-4-6
```

### 5. 配置 MCP (可选)

如果你需要使用 MCP 服务器（如 GitHub 集成），创建 `.mcp.json` 文件：

```json
{
  "mcpServers": {
    "github": {
      "type": "stdio",
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your-github-token-here"
      }
    }
  }
}
```

## 使用

启动交互式 CLI：

```bash
my_claude
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
│       ├── mcp/             # MCP 支持
│       │   ├── config.py
│       │   ├── server.py
│       │   └── tools/
│       └── skills/          # Skill 系统
│           ├── config.py
│           └── manager.py
├── my_project/              # 默认工作目录
├── pyproject.toml
├── .env.example
└── README.md
```

## 开发

### 运行测试

```bash
python -m pytest
```

### 代码格式化

```bash
pip install black isort
black src/
isort src/
```

## 许可证

MIT License

## 致谢

- [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk)
- [Model Context Protocol](https://modelcontextprotocol.io/)