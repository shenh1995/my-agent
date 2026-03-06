#!/usr/bin/env python3
"""测试多模态消息（图片）处理"""

import os
import sys
import json
import base64
import anyio
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from claude_agent_sdk import query, ClaudeAgentOptions


async def test_image_message():
    """测试发送图片消息"""

    # 读取测试图片
    image_path = "/Users/shenhong/go/source/my-agent/my_project/.images/screenshot_to_read.png"
    with open(image_path, "rb") as f:
        image_data = f.read()

    base64_data = base64.b64encode(image_data).decode()

    # 创建消息流
    async def message_stream():
        yield {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64_data,
                        },
                    },
                    {"type": "text", "text": "请描述这张图片的内容"},
                ],
            },
            "parent_tool_use_id": None,
            "session_id": "",
        }

    # 配置选项
    options = ClaudeAgentOptions(
        permission_mode="default",
        cwd="./my_project",
        max_turns=1,
    )

    print("发送包含图片的消息...")
    print(f"图片 base64 长度: {len(base64_data)}")

    # 发送请求
    async for message in query(prompt=message_stream(), options=options):
        msg_type = type(message).__name__
        print(f"\n收到消息类型: {msg_type}")

        if msg_type == "AssistantMessage":
            for block in message.content:
                block_type = type(block).__name__
                if block_type == "TextBlock" and hasattr(block, "text"):
                    print(f"Claude: {block.text[:200]}...")
                elif block_type == "ThinkingBlock" and hasattr(block, "thinking"):
                    print(f"[思考] {block.thinking[:200]}...")
        elif msg_type == "ResultMessage":
            print(f"结果: {message.result[:200] if message.result else 'None'}...")


if __name__ == "__main__":
    anyio.run(test_image_message)