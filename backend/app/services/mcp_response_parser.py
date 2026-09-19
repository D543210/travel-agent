"""MCP响应解析工具"""

import json
from typing import Any

class MCPResponseParseError(ValueError):
    """MCP响应无法解析时抛出异常。"""

def extract_json_value(raw:Any)->Any:
    """从MCP响应中提取JSON值。

    Args:
        raw: MCP响应的原始数据。

    Returns:
        提取的JSON值。

    Raises:
        MCPResponseParserError: 如果无法解析MCP响应。


    支持：
    1. 已经是dict或list的数据
    2. 带说明文字的JSON字符串
    3. 顶层为对象或数组的JSON
    """

    #如果是字典或者列表，直接原样返回
    if isinstance(raw,(dict,list)):
        return raw

    #如果不是字典或者列表，判断是否为字符串
    if not isinstance(raw,str):
        raise MCPResponseParseError(f"无法解析MCP响应: {raw}")

    #是字符串，则解析
    raw = raw.strip()

    if not raw:
        raise MCPResponseParseError("无法解析MCP响应: 空字符串")

    decoder = json.JSONDecoder()

    for index,char in enumerate(raw):
        if char not in "{[":
            continue

        try:
            value,_ = decoder.raw_decode(raw[index:])

        except json.JSONDecodeError:
            continue

        if isinstance(value,(dict,list)):
            return value

    raise MCPResponseParseError(f"无法解析MCP响应: {raw}")
        

