from __future__ import annotations

import re


def normalize_bullets_to_ordered(text: str) -> str:
    """
    将 Markdown 顶层无序列表 (- / •) 转为 1. 2. 3. 的编号列表。
    只处理行首匹配的情况，其他内容保持原状。
    """
    lines = text.splitlines()
    new_lines: list[str] = []
    index = 1

    for line in lines:
        if re.match(r"^\s*[-•]\s+", line):
            content = re.sub(r"^\s*[-•]\s+", "", line)
            new_lines.append(f"{index}. {content}")
            index += 1
        else:
            new_lines.append(line)

    return "\n".join(new_lines)


def is_chinese_heavy(text: str, threshold: float = 0.2) -> bool:
    """
    粗略判断中文字符占比是否高于阈值。
    """
    if not text:
        return False
    chinese_chars = re.findall(r"[\u4e00-\u9fff]", text)
    ratio = len(chinese_chars) / max(len(text), 1)
    return ratio > threshold

