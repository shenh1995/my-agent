# My Agent

一个基于 [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk) 的交互式命令行工具，提供强大的 AI 助手功能。

## 特性

- **交互式 CLI** - 美观的命令行界面，支持多行输入和语法高亮
- **一键安装** - 自动下载预编译二进制文件，无需配置 Python 环境
- **首次运行向导** - 交互式配置 API Key、Base URL 和模型
- **MCP 支持** - 支持 Model Context Protocol，可扩展工具能力
- **Skill 系统** - 通过斜杠命令执行预定义任务
- **Plan Mode** - 只读探索模式，生成计划供审批后执行
- **项目级指令** - 支持 CLAUDE.md 文件定义项目特定的 AI 行为规则
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
| `/reload` | 重新加载项目指令 (CLAUDE.md) |
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

### 项目级指令 (CLAUDE.md)

你可以在项目根目录创建 `CLAUDE.md` 文件来定义项目特定的 AI 行为规则。这些指令会在每次对话中自动注入到系统提示中。

#### 创建 CLAUDE.md

在项目根目录创建 `CLAUDE.md` 文件：

```markdown
# 项目指令

## 代码风格
- 使用 TypeScript 编写所有代码
- 遵循 ESLint 规则
- 函数必须有 JSDoc 注释

## 测试
- 使用 Jest 进行单元测试
- 测试覆盖率要求 80% 以上

## Git 规范
- 提交信息遵循 Conventional Commits
- 分支命名: feature/xxx, fix/xxx
```

#### 功能特点

- **自动查找**：从当前目录向上查找 `CLAUDE.md`，直到 git 根目录
- **支持多个文件**：子目录可以有独立的 `CLAUDE.md`，会与父目录的合并
- **启动加载**：启动时会自动加载并显示加载信息
- **热重载**：使用 `/reload` 命令重新加载项目指令

#### 文件查找顺序

1. 当前工作目录的 `CLAUDE.md`
2. 父目录的 `CLAUDE.md`（向上查找，直到 git 根目录）
3. 子目录的指令优先级高于父目录

#### 使用示例

```bash
# 项目结构
my-project/
├── CLAUDE.md          # 项目级指令
├── src/
│   └── CLAUDE.md      # src 目录特定指令
└── tests/

# 在 my-project 目录运行时，会加载两个 CLAUDE.md 的内容
# 在 src 目录运行时，优先使用 src/CLAUDE.md
```

### Hooks 配置

Hooks 允许你在特定事件发生时执行自定义脚本，例如在工具调用前后、用户提交提示时等。

在 `~/.claude/hooks.json` 或项目目录的 `.claude/hooks.json` 中配置：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "command": "echo '即将执行 Bash 命令' >&2",
        "timeout": 5,
        "enabled": true
      }
    ],
    "PostToolUse": [
      {
        "matcher": "*",
        "command": "echo '工具执行完成: $CLAUDE_TOOL_NAME' >&2",
        "enabled": true
      }
    ],
    "UserPromptSubmit": []
  }
}
```

#### 支持的 Hook 事件

| 事件 | 触发时机 |
|------|----------|
| `PreToolUse` | 工具调用前 |
| `PostToolUse` | 工具调用后 |
| `PostToolUseFailure` | 工具调用失败后 |
| `UserPromptSubmit` | 用户提交提示时 |
| `Stop` | 会话停止时 |
| `SubagentStart` | 子智能体启动时 |
| `SubagentStop` | 子智能体停止时 |
| `PreCompact` | 压缩对话前 |
| `Notification` | 通知事件 |
| `PermissionRequest` | 权限请求时 |

#### Hook 配置字段

| 字段 | 说明 |
|------|------|
| `matcher` | 匹配器，支持工具名、通配符 `*` 或正则表达式 |
| `command` | 要执行的 shell 命令 |
| `timeout` | 超时时间（秒），默认 60 |
| `enabled` | 是否启用，默认 true |

#### 环境变量

Hook 命令执行时可以使用以下环境变量：

- `CLAUDE_HOOK_EVENT` - 事件名称
- `CLAUDE_SESSION_ID` - 会话 ID
- `CLAUDE_CWD` - 当前工作目录
- `CLAUDE_TOOL_NAME` - 工具名称（工具相关事件）
- `CLAUDE_TOOL_INPUT` - 工具输入（JSON 格式）
- `CLAUDE_PROMPT` - 用户提示（UserPromptSubmit 事件）

#### Hook 输出

Hook 可以通过 stdout 返回 JSON 来控制行为：

```json
{
  "decision": "block",
  "reason": "阻止执行的原因"
}
```

- `decision: "block"` - 阻止操作继续执行
- `systemMessage` - 显示给用户的系统消息

## 项目结构

```
my-agent/
├── src/
│   └── my_agent/
│       ├── cli.py                 # 主入口
│       ├── ui.py                  # UI 显示
│       ├── input.py               # 输入处理
│       ├── commands.py            # 命令处理
│       ├── permissions.py         # 权限管理
│       ├── image.py               # 图片分析
│       ├── plan_mode.py           # Plan Mode
│       ├── plan_ui.py             # Plan Mode UI
│       ├── task_manager.py        # 任务管理
│       ├── highlight.py           # 语法高亮
│       ├── setup_wizard.py        # 首次运行配置向导
│       ├── project_instructions.py # 项目级指令支持
│       ├── mcp/                   # MCP 支持
│       │   ├── config.py
│       │   ├── server.py
│       │   └── tools/
│       ├── skills/                # Skill 系统
│       │   ├── config.py
│       │   └── manager.py
│       └── hooks/                 # Hook 系统
│           ├── __init__.py
│           └── config.py
├── .github/
│   └── workflows/
│       └── release.yml            # GitHub Actions 自动发布
├── build.spec                     # PyInstaller 构建配置
├── run.py                         # PyInstaller 入口
├── install.sh                     # 安装脚本
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