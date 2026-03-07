"""首次运行配置向导"""

import os
from pathlib import Path
from typing import Optional


CONFIG_DIR = Path.home() / ".claude" / "my-agent"
CONFIG_FILE = CONFIG_DIR / ".env"


def check_config_exists() -> bool:
    """检查配置文件是否存在且有效

    Returns:
        True 如果配置文件存在且包含必要的配置项
    """
    if not CONFIG_FILE.exists():
        return False

    # 检查必要的配置项
    required_keys = [
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_MODEL",
    ]

    existing_keys = set()
    try:
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key = line.split('=')[0].strip()
                    existing_keys.add(key)
    except Exception:
        return False

    return all(key in existing_keys for key in required_keys)


def get_config_value(key: str) -> Optional[str]:
    """获取配置值

    Args:
        key: 配置键名

    Returns:
        配置值，如果不存在则返回 None
    """
    if not CONFIG_FILE.exists():
        return None

    try:
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        current_key = parts[0].strip()
                        value = parts[1].strip()
                        if current_key == key:
                            return value
    except Exception:
        pass

    return None


def run_setup_wizard() -> dict:
    """运行交互式配置向导

    Returns:
        包含配置项的字典
    """
    print("\n" + "=" * 50)
    print("  欢迎使用 My Agent!")
    print("  首次运行需要进行配置")
    print("=" * 50 + "\n")

    # 获取 API Key
    api_key = ""
    while not api_key:
        api_key = input("请输入 API Key: ").strip()
        if not api_key:
            print("\033[1;31m  API Key 不能为空，请重新输入\033[0m\n")

    # 获取 Base URL
    base_url = ""
    while not base_url:
        base_url = input("请输入 Base URL: ").strip()
        if not base_url:
            print("\033[1;31m  Base URL 不能为空，请重新输入\033[0m\n")

    # 获取模型名称
    model = ""
    while not model:
        model = input("请输入模型名称: ").strip()
        if not model:
            print("\033[1;31m  模型名称不能为空，请重新输入\033[0m\n")

    return {
        "ANTHROPIC_API_KEY": api_key,
        "ANTHROPIC_BASE_URL": base_url,
        "ANTHROPIC_MODEL": model,
    }


def save_config(config: dict) -> None:
    """保存配置到文件

    Args:
        config: 包含配置项的字典
    """
    # 创建配置目录
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # 写入配置文件
    with open(CONFIG_FILE, 'w') as f:
        f.write("# My Agent 配置\n")
        f.write("# 此文件由首次运行向导自动生成\n\n")
        for key, value in config.items():
            f.write(f"{key}={value}\n")

    print(f"\n\033[1;32m配置已保存到: {CONFIG_FILE}\033[0m\n")


def load_config_to_env() -> None:
    """加载配置到环境变量"""
    if not CONFIG_FILE.exists():
        return

    try:
        with open(CONFIG_FILE, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    parts = line.split('=', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip()
                        # 只有当环境变量未设置时才设置
                        if key not in os.environ:
                            os.environ[key] = value
    except Exception:
        pass