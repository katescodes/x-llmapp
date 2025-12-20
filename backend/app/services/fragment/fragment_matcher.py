"""
FragmentTitleMatcher - 范本标题匹配器
用于将章节标题归一化并匹配到 FragmentType
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from app.services.fragment.fragment_type import FragmentType


class FragmentTitleMatcher:
    """范本标题匹配器"""
    
    def __init__(self):
        self._dict: Dict[FragmentType, List[str]] = {}
        self._load_dict()
    
    def _load_dict(self):
        """加载匹配字典"""
        dict_file = Path(__file__).parent / "fragment_dict_zh_CN.json"
        if not dict_file.exists():
            return
        
        try:
            with open(dict_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for key, synonyms in data.items():
                try:
                    ftype = FragmentType[key]
                    self._dict[ftype] = synonyms
                except KeyError:
                    continue
        except Exception:
            pass
    
    def normalize(self, s: str) -> str:
        """
        归一化标题
        - 去空白、全角半角统一
        - 删除括号内容
        - 删除尾部关键词
        - 去常见编号前缀
        """
        if not s:
            return ""
        
        # 去空白（包括全角空格）
        x = s.strip()
        x = re.sub(r'[\u3000\s]+', '', x)
        
        # 删除括号内容（中文括号）
        x = re.sub(r'（[^）]*）', '', x)
        # 删除括号内容（英文括号）
        x = re.sub(r'\([^)]*\)', '', x)
        
        # 去常见编号前缀
        x = re.sub(r'^(第[一二三四五六七八九十0-9]+[章节篇编])', '', x)
        x = re.sub(r'^\d+(\.\d+)*\.?\s*', '', x)
        
        # 删除尾部关键词
        x = re.sub(r'(格式|样本|范本|示例|模板|附件|表格?|\(表\)|（表）)$', '', x)
        
        # 删除标点符号
        x = re.sub(r'[：:。．\.、,，;；]', '', x)
        
        # 同义词归一化（增强匹配率）
        x = x.replace("法定代表人", "法人")
        x = x.replace("授权委托书", "授权书")
        x = x.replace("法定代表人授权书", "法人授权书")
        
        return x.strip()
    
    def match_type(self, title_norm: str) -> Optional[FragmentType]:
        """
        根据归一化标题匹配 FragmentType
        
        Args:
            title_norm: 归一化后的标题
            
        Returns:
            匹配到的 FragmentType，如果没有匹配则返回 None
        """
        if not title_norm:
            return None
        
        # 匹配结果：(FragmentType, synonym_length)
        matches: List[tuple[FragmentType, int]] = []
        
        for ftype, synonyms in self._dict.items():
            for synonym in synonyms:
                syn_norm = self.normalize(synonym)
                if not syn_norm:
                    continue
                
                # 精确匹配
                if title_norm == syn_norm:
                    matches.append((ftype, len(syn_norm)))
                # 包含匹配
                elif syn_norm in title_norm or title_norm in syn_norm:
                    matches.append((ftype, len(syn_norm)))
        
        if not matches:
            return None
        
        # 按 synonym 长度排序（更具体的优先）
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[0][0]
