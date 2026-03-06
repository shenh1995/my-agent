"""代码语法高亮功能"""

import re
from pygments import highlight
from pygments.lexers import get_lexer_by_name, guess_lexer, TextLexer
from pygments.formatters import Terminal256Formatter
from pygments.util import ClassNotFound


# 代码高亮格式化器
_formatter = Terminal256Formatter(style='monokai')


def highlight_code(code: str, language: str = None) -> str:
    """对代码进行语法高亮

    Args:
        code: 要高亮的代码
        language: 语言名称（可选）

    Returns:
        高亮后的代码字符串
    """
    try:
        if language:
            lexer = get_lexer_by_name(language, stripall=True)
        else:
            lexer = guess_lexer(code)
    except ClassNotFound:
        lexer = TextLexer()

    return highlight(code, lexer, _formatter)


def format_text_with_code(text: str) -> str:
    """处理文本中的代码块，应用语法高亮

    支持 ```language 格式的代码块

    Args:
        text: 包含代码块的文本

    Returns:
        格式化后的文本
    """
    # 匹配 ```language\ncode\n``` 格式的代码块
    pattern = r'```(\w*)\n(.*?)```'

    def replace_code_block(match):
        language = match.group(1) or None
        code = match.group(2)
        # 移除末尾多余的换行
        code = code.rstrip('\n')
        highlighted = highlight_code(code, language)
        # 添加代码块边框
        return f"\n\033[90m{'─' * 40}\033[0m\n{highlighted}\033[90m{'─' * 40}\033[0m\n"

    return re.sub(pattern, replace_code_block, text, flags=re.DOTALL)