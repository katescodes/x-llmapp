#!/usr/bin/env python3
"""删除extract_v2_service.py中的废弃方法"""

file_path = '/aidata/x-llmapp1/backend/app/works/tender/extract_v2_service.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 删除第1595-1797行（prepare_tender_for_audit 及其辅助方法）
# Python索引从0开始，所以是1594:
new_lines = lines[:1594]

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"✅ 已删除 {len(lines) - len(new_lines)} 行废弃方法")
print(f"原文件: {len(lines)} 行")
print(f"新文件: {len(new_lines)} 行")

