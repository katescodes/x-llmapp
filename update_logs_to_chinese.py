#!/usr/bin/env python3
"""
更新日志信息为中文
"""
import re

# project_info_prompt_builder.py的日志更新
prompt_builder_updates = [
    # 日志信息中英文混合的部分改为全中文
    (
        r'logger\.info\(\s*f"P0 response parsed: stage=\{self\.stage\}, "\s*f"fields=\{len\(standardized\)\}, evidence_fields=\{len\(\[e for e in evidence_map\.values\(\) if e\]\)\}"\s*\)',
        'logger.info(\n                f"P0响应已解析: stage={self.stage}, "\n                f"提取字段数={len(standardized)}, 含证据字段数={len([e for e in evidence_map.values() if e])}"\n            )'
    ),
    (
        r'logger\.info\(\s*f"P1 response parsed: stage=\{self\.stage\}, "\s*f"supplements=\{len\(supplements\)\}"\s*\)',
        'logger.info(\n                f"P1响应已解析: stage={self.stage}, "\n                f"补充字段数={len(supplements)}"\n            )'
    ),
    (
        r'logger\.info\(\s*f"Merged P0\+P1: stage=\{self\.stage\}, "\s*f"total_fields=\{len\(merged_data\)\}, "\s*f"evidence_segments=\{len\(all_evidence_ids\)\}, "\s*f"p1_supplements=\{len\(supplements\)\}"\s*\)',
        'logger.info(\n                f"P0+P1已合并: stage={self.stage}, "\n                f"总字段数={len(merged_data)}, "\n                f"证据片段数={len(all_evidence_ids)}, "\n                f"P1补充数={len(supplements)}"\n            )'
    ),
    (
        r'logger\.info\(\s*f"Converted to schema: stage=\{self\.stage\}, key=\{self\.stage_key\}, "\s*f"fields=\{len\(data\)\}"\s*\)',
        'logger.info(\n                f"已转换为Schema格式: stage={self.stage}, key={self.stage_key}, "\n                f"字段数={len(data)}"\n            )'
    ),
]

# project_info_extractor.py的日志更新
extractor_updates = [
    (
        r'logger\.info\(f"ProjectInfoExtractor initialized with checklist: \{self\.checklist_path\}"\)',
        'logger.info(f"项目信息提取器已初始化，checklist配置: {self.checklist_path}")'
    ),
    (
        r'logger\.info\(\s*f"Loaded checklist: \{config\.get\(\'template_name\'\)\}, "\s*f"version=\{config\.get\(\'version\'\)\}, "\s*f"stages=\{config\.get\(\'metadata\', \{\}\)\.get\(\'total_stages\', 0\)\}"\s*\)',
        'logger.info(\n                f"已加载checklist: {config.get(\'template_name\')}, "\n                f"版本={config.get(\'version\')}, "\n                f"stage数量={config.get(\'metadata\', {}).get(\'total_stages\', 0)}"\n            )'
    ),
    (
        r'logger\.info\(f"Extracted \{len\(stages\)\} stage configs"\)',
        'logger.info(f"已提取{len(stages)}个stage配置")'
    ),
    (
        r'logger\.info\(\s*f"Extracting stage \{stage\} \(\{stage_name\}\), "\s*f"enable_p1=\{enable_p1\}, has_context_info=\{context_info is not None\}"\s*\)',
        'logger.info(\n                f"正在提取stage {stage} ({stage_name}), "\n                f"启用P1={enable_p1}, 有前序上下文={context_info is not None}"\n            )'
    ),
]

print("日志更新映射已准备")
print(f"prompt_builder更新数: {len(prompt_builder_updates)}")
print(f"extractor更新数: {len(extractor_updates)}")
print("\n请手动应用这些更新，或者使用sed/awk工具批量替换")

