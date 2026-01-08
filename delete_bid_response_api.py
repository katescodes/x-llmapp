#!/usr/bin/env python3
"""删除tender.py中的投标响应API端点"""

file_path = '/aidata/x-llmapp1/backend/app/routers/tender.py'

with open(file_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# 删除第1106-1380行（Python索引从0开始，所以是1105-1379）
# 保留注释行（第1106行的 # ==== 投标响应抽取 ====）
new_lines = lines[:1105] + lines[1380:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print(f"✅ 已删除 {1380-1105} 行投标响应API代码")
print(f"原文件: {len(lines)} 行")
print(f"新文件: {len(new_lines)} 行")

