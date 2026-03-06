"""Web 获取工具

提供网页内容获取和处理功能，包括：
- HTTP/HTTPS 请求
- HTML 转 Markdown
- AI 内容处理
- 重定向处理
"""

import os
import re
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from claude_agent_sdk import tool

# 延迟导入，避免未安装时报错
_httpx = None
_markdownify = None


def _get_httpx():
    """延迟加载 httpx"""
    global _httpx
    if _httpx is None:
        try:
            import httpx
            _httpx = httpx
        except ImportError:
            raise ImportError(
                "httpx 未安装。请运行: pip install httpx"
            )
    return _httpx


def _get_markdownify():
    """延迟加载 markdownify"""
    global _markdownify
    if _markdownify is None:
        try:
            from markdownify import markdownify as md
            _markdownify = md
        except ImportError:
            raise ImportError(
                "markdownify 未安装。请运行: pip install markdownify"
            )
    return _markdownify


# 默认超时时间（秒）
DEFAULT_TIMEOUT = 30

# 最大重定向次数
MAX_REDIRECTS = 5

# 最大内容长度（字符）
MAX_CONTENT_LENGTH = 100000


def validate_url(url: str) -> tuple[bool, Optional[str]]:
    """验证 URL 格式

    Args:
        url: 要验证的 URL

    Returns:
        (是否有效, 错误信息)
    """
    if not url:
        return False, "URL 不能为空"

    # 自动添加协议
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    try:
        parsed = urlparse(url)
        if not parsed.netloc:
            return False, "无效的 URL：缺少域名"

        # 只允许 http 和 https
        if parsed.scheme not in ("http", "https"):
            return False, f"不支持的协议: {parsed.scheme}，只支持 HTTP/HTTPS"

        return True, None
    except Exception as e:
        return False, f"URL 解析错误: {str(e)}"


def normalize_url(url: str) -> str:
    """标准化 URL

    - 自动升级 HTTP 到 HTTPS
    - 移除末尾斜杠

    Args:
        url: 原始 URL

    Returns:
        标准化后的 URL
    """
    # 自动添加协议
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # 升级 HTTP 到 HTTPS
    if url.startswith("http://"):
        url = "https://" + url[7:]

    return url


def html_to_markdown(html_content: str) -> str:
    """将 HTML 转换为 Markdown

    Args:
        html_content: HTML 内容

    Returns:
        Markdown 文本
    """
    markdownify = _get_markdownify()
    return markdownify(html_content, heading_style="atx")


def process_with_ai(prompt: str, content: str) -> str:
    """使用 AI 处理内容

    Args:
        prompt: 处理提示词
        content: 网页内容

    Returns:
        AI 处理后的结果
    """
    from anthropic import Anthropic

    # 获取客户端配置
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    base_url = os.environ.get("ANTHROPIC_IMAGE_URL")

    if not api_key:
        return "错误：未设置 ANTHROPIC_API_KEY 环境变量"

    client = Anthropic(api_key=api_key, base_url=base_url)

    # 截断过长的内容
    if len(content) > MAX_CONTENT_LENGTH:
        content = content[:MAX_CONTENT_LENGTH] + "\n\n... [内容已截断]"

    model = os.environ.get("ANTHROPIC_IMAGE_MODEL", "glm-5")

    try:
        response = client.messages.create(
            model=model,
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": f"{prompt}\n\n网页内容：\n{content}"
            }]
        )

        # 处理响应内容
        result_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                result_text += block.text
            elif hasattr(block, 'thinking'):
                result_text += block.thinking

        return result_text
    except Exception as e:
        return f"AI 处理错误: {str(e)}"


@tool(
    "web_fetch",
    "获取网页内容并使用 AI 模型处理。支持将 HTML 转换为 Markdown，并可选使用 prompt 参数让 AI 提取特定信息。",
    {
        "url": str,
        "prompt": str,
    }
)
async def web_fetch(args: Dict[str, Any]) -> Dict[str, Any]:
    """获取网页内容

    Args:
        url: 要获取的 URL（必填）
        prompt: 用于处理内容的提示词（可选，如"提取前5条新闻标题"）

    Returns:
        网页内容或 AI 处理结果
    """
    url = args.get("url", "")
    prompt = args.get("prompt", "")

    if not url:
        return {
            "content": [{"type": "text", "text": "错误：缺少 url 参数"}],
            "isError": True
        }

    # 验证 URL
    is_valid, error_msg = validate_url(url)
    if not is_valid:
        return {
            "content": [{"type": "text", "text": f"错误：{error_msg}"}],
            "isError": True
        }

    # 标准化 URL
    url = normalize_url(url)

    httpx = _get_httpx()

    try:
        # 发起请求
        with httpx.Client(
            follow_redirects=True,
            max_redirects=MAX_REDIRECTS,
            timeout=DEFAULT_TIMEOUT,
        ) as client:
            response = client.get(url)

            # 检查状态码
            if response.status_code >= 400:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"HTTP 错误: {response.status_code}\nURL: {url}"
                    }],
                    "isError": True
                }

            # 获取内容类型
            content_type = response.headers.get("content-type", "")

            # 获取原始内容
            html_content = response.text

            # 检查内容长度
            if len(html_content) > MAX_CONTENT_LENGTH * 2:
                html_content = html_content[:MAX_CONTENT_LENGTH * 2]

            # 转换为 Markdown
            markdown_content = html_to_markdown(html_content)

            # 如果有 prompt，使用 AI 处理
            if prompt:
                ai_result = process_with_ai(prompt, markdown_content)
                result = f"URL: {url}\n\n提示词: {prompt}\n\n处理结果:\n{ai_result}"
            else:
                result = f"URL: {url}\n\n{markdown_content}"

            return {
                "content": [{"type": "text", "text": result}],
                "isError": False
            }

    except httpx.TimeoutException:
        return {
            "content": [{
                "type": "text",
                "text": f"请求超时（{DEFAULT_TIMEOUT}秒）\nURL: {url}"
            }],
            "isError": True
        }
    except httpx.TooManyRedirects:
        return {
            "content": [{
                "type": "text",
                "text": f"重定向次数过多（超过 {MAX_REDIRECTS} 次）\nURL: {url}"
            }],
            "isError": True
        }
    except httpx.RequestError as e:
        return {
            "content": [{
                "type": "text",
                "text": f"网络请求错误: {str(e)}\nURL: {url}"
            }],
            "isError": True
        }
    except Exception as e:
        return {
            "content": [{
                "type": "text",
                "text": f"获取网页时出错: {str(e)}\nURL: {url}"
            }],
            "isError": True
        }


# 导出
__all__ = ["web_fetch"]