"""HTML 相关工具函数。"""

from __future__ import annotations

import json


def safe_json_for_script(data: object) -> str:
    """将数据序列化为可内联到 <script> 标签的 JSON 字符串。

    json.dumps 默认不转义 HTML 敏感字符，将包含 '</script>' 的字符串
    内联到 <script> 块时会导致 HTML 解析器提前结束脚本块，引发注入。
    本函数通过 Unicode 转义消除该风险：
    - '<' / '>' 转义为 \\u003c / \\u003e，防止标签解析
    - '/' 转义为 \\u002f，对抗 '</script>' 变体绕过
    - '&' 转义为 \\u0026，防止 HTML 实体解析
    生成的 Unicode 转义序列是合法 JSON，JS 引擎正确解析，HTML 解析器不识别为标签。
    """
    return (
        json.dumps(data, ensure_ascii=False)
        .replace("&", r"\u0026")
        .replace("<", r"\u003c")
        .replace(">", r"\u003e")
        .replace("/", r"\u002f")
    )
