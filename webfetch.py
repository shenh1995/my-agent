"""
网页获取和分析脚本
使用 httpx 获取网页，markdownify 转换为 Markdown，然后使用 AI 分析
"""

import os
from anthropic import Anthropic

# 延迟导入
_httpx = None
_markdownify = None


def get_httpx():
    global _httpx
    if _httpx is None:
        import httpx
        _httpx = httpx
    return _httpx


def get_markdownify():
    global _markdownify
    if _markdownify is None:
        from markdownify import markdownify as md
        _markdownify = md
    return _markdownify


def fetch_url(url: str, timeout: int = 30) -> str:
    """
    获取网页内容并转换为 Markdown

    Args:
        url: 网页 URL
        timeout: 超时时间（秒）

    Returns:
        Markdown 格式的网页内容
    """
    httpx = get_httpx()
    markdownify = get_markdownify()

    # 自动添加协议
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        response = client.get(url)
        response.raise_for_status()
        html = response.text
        return markdownify(html, heading_style="atx")


def fetch_and_analyze(
    url: str,
    prompt: str = "请分析这个网页的内容"
) -> str:
    """
    获取并分析网页内容

    Args:
        url: 要获取的网页 URL
        prompt: 分析提示词

    Returns:
        模型的分析结果
    """
    # 1. 获取网页内容
    print(f"正在获取网页: {url}")
    markdown_content = fetch_url(url)

    # 截断过长内容
    max_length = 50000
    if len(markdown_content) > max_length:
        markdown_content = markdown_content[:max_length] + "\n\n... [内容已截断]"

    print(f"网页内容长度: {len(markdown_content)} 字符")

    # 2. 调用 AI 分析
    print("正在调用 AI 分析...")
    client = Anthropic(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        base_url=os.environ.get("ANTHROPIC_BASE_URL")
    )

    model = os.environ.get("ANTHROPIC_MODEL", "glm-5")

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": f"{prompt}\n\n网页内容：\n{markdown_content}",
            }
        ]
    )

    # 处理响应内容
    result_text = ""
    for block in response.content:
        if hasattr(block, 'text'):
            result_text += block.text
        elif hasattr(block, 'thinking'):
            result_text += block.thinking

    return result_text


def main():
    """主函数"""
    url = "https://example.com"
    prompt = "请分析这个网页的主要内容，并用中文总结"

    print(f"正在获取并分析网页: {url}")
    print(f"提示词: {prompt}")
    print("-" * 50)

    try:
        result = fetch_and_analyze(url, prompt)
        print("-" * 50)
        print("分析结果:")
        print(result)
    except Exception as e:
        print(f"错误: {e}")


if __name__ == "__main__":
    main()