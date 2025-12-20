#!/usr/bin/env python3
import json

# 测试带前导空格的情况
test_cases = [
    ("```json\n{\"test\": 1}\n```", "Normal case"),
    (" ```json\n{\"test\": 1}\n```", "Leading space"),
    ("\n```json\n{\"test\": 1}\n```", "Leading newline"),
    ("\t```json\n{\"test\": 1}\n```", "Leading tab"),
]

def extract_json(text: str) -> dict:
    """复制 json_utils.py 中的逻辑"""
    text = text.strip()
    
    if "```json" in text:
        start_marker = text.find("```json")
        start = start_marker + 7
        while start < len(text) and text[start] in (' ', '\n', '\r', '\t'):
            start += 1
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    
    return json.loads(text)

for test_text, desc in test_cases:
    print(f"\n{desc}:")
    print(f"  Input: {repr(test_text[:30])}")
    try:
        result = extract_json(test_text)
        print(f"  ✓ Success: {result}")
    except Exception as e:
        print(f"  ✗ Failed: {e}")

