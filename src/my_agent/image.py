"""图片处理功能"""

import os
import re
import base64
import mimetypes
import shutil
from typing import Optional, Tuple, List, Dict, Any

from anthropic import Anthropic


# 支持的图片格式
SUPPORTED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp'}


def get_anthropic_client() -> Anthropic:
    """获取 Anthropic 客户端实例

    Returns:
        配置好的 Anthropic 客户端
    """
    return Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_IMAGE_URL")
    )


def analyze_image(text: str, image_path: str) -> str:
    """使用 Anthropic API 分析图片内容

    Args:
        text: 用户的问题或请求
        image_path: 图片文件路径

    Returns:
        模型的分析结果
    """
    client = get_anthropic_client()

    # 读取并编码图像
    base64_data, mime_type = encode_image_to_base64(image_path)

    # 构建消息
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": text
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64_data
                    }
                }
            ]
        }
    ]

    # 调用模型
    model = os.environ.get("ANTHROPIC_IMAGE_MODEL", "glm-5")
    response = client.messages.create(
        model=model,
        max_tokens=1000,
        messages=messages
    )

    # 处理响应内容（可能包含 TextBlock 或 ThinkingBlock）
    result_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            result_text += block.text
        elif hasattr(block, 'thinking'):
            result_text += block.thinking

    return result_text


def analyze_images(text: str, image_paths: List[str]) -> str:
    """使用 Anthropic API 分析多张图片

    Args:
        text: 用户的问题或请求
        image_paths: 图片文件路径列表

    Returns:
        模型的分析结果
    """
    client = get_anthropic_client()

    # 构建内容块
    content_blocks = [{"type": "text", "text": text}]

    for image_path in image_paths:
        base64_data, mime_type = encode_image_to_base64(image_path)
        content_blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": mime_type,
                "data": base64_data
            }
        })

    # 构建消息
    messages = [{"role": "user", "content": content_blocks}]

    # 调用模型
    model = os.environ.get("ANTHROPIC_IMAGE_MODEL", "glm-5")
    response = client.messages.create(
        model=model,
        max_tokens=1000,
        messages=messages
    )

    # 处理响应内容
    result_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            result_text += block.text
        elif hasattr(block, 'thinking'):
            result_text += block.thinking

    return result_text


def is_image_file(file_path: str) -> bool:
    """检查文件是否为支持的图片格式

    Args:
        file_path: 文件路径

    Returns:
        是否为图片文件
    """
    ext = os.path.splitext(file_path.lower())[1]
    return ext in SUPPORTED_IMAGE_EXTENSIONS


def encode_image_to_base64(file_path: str) -> Tuple[str, str]:
    """将图片文件编码为 base64

    Args:
        file_path: 图片文件路径

    Returns:
        (base64编码字符串, MIME类型)
    """
    # 检测 MIME 类型
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'image/png'  # 默认类型

    with open(file_path, 'rb') as f:
        image_data = f.read()

    base64_str = base64.b64encode(image_data).decode('utf-8')
    return base64_str, mime_type


def parse_image_path(prompt: str) -> Optional[str]:
    """从用户输入中解析图片路径

    支持格式:
    - [image][Image: source: /path/to/image.png]
    - [Image: source: /path/to/image.png]
    - file:///path/to/image.png
    - /path/to/image.png (直接拖拽的文件路径)

    Args:
        prompt: 用户输入

    Returns:
        图片路径或 None
    """
    # 处理 [image][Image: source: /path/to/image.png] 格式
    image_match = re.search(r'\[image\]\s*\[Image:\s*source:\s*([^\]]+)\]', prompt)
    if image_match:
        return image_match.group(1).strip()

    # 处理 [Image: source: /path/to/image.png] 格式
    image_match = re.search(r'\[Image:\s*source:\s*([^\]]+)\]', prompt)
    if image_match:
        return image_match.group(1).strip()

    # 处理 file:// URI 格式
    if prompt.startswith('file://'):
        return prompt[7:]  # 移除 'file://' 前缀

    # 处理普通文件路径（直接拖拽到终端的情况）
    if os.path.isfile(prompt) and is_image_file(prompt):
        return prompt

    return None


def format_image_prompt(image_path: str) -> str:
    """将图片路径格式化为标准显示格式

    Args:
        image_path: 图片文件路径

    Returns:
        格式化后的字符串，如: [image][Image: source: /path/to/image.png]
    """
    return f"[image][Image: source: {image_path}]"


def copy_image_to_project(image_path: str, project_dir: str) -> str:
    """将图片复制到项目目录

    Args:
        image_path: 原图片路径
        project_dir: 项目目录

    Returns:
        复制后的相对路径
    """
    project_image_dir = os.path.join(project_dir, ".images")
    os.makedirs(project_image_dir, exist_ok=True)
    image_filename = os.path.basename(image_path)
    dest_path = os.path.join(project_image_dir, image_filename)
    shutil.copy2(image_path, dest_path)
    return f".images/{image_filename}"