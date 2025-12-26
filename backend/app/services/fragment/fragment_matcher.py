"""
FragmentTitleMatcher - 范本标题匹配器
用于将章节标题归一化并匹配到 FragmentType
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.services.fragment.fragment_type import FragmentType


class FragmentTitleMatcher:
    """范本标题匹配器（增强版：支持置信度、同义词、模糊匹配）"""
    
    def __init__(self):
        self._dict: Dict[FragmentType, List[str]] = {}
        self._synonyms: Dict[str, List[str]] = {}
        self._load_dict()
        self._load_synonyms()
    
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
    
    def _load_synonyms(self):
        """
        加载同义词表（增强匹配能力）
        
        同义词用于处理非标准标题，提升匹配准确率
        """
        self._synonyms = {
            # 投标函相关
            "投标函": ["投标书", "投标文件", "投标申请书", "投标报价函", "响应函"],
            "投标书": ["投标函", "投标文件"],
            
            # 授权委托书相关
            "授权委托书": ["法人授权书", "授权书", "委托书", "法定代表人授权", "法定代表人授权委托书"],
            "授权书": ["授权委托书", "法人授权书", "委托书"],
            "法人授权书": ["授权委托书", "授权书", "法定代表人授权书"],
            
            # 保证金相关
            "保证金": ["投标保证金", "保证金凭证", "保函", "投标担保"],
            "保函": ["投标保函", "保证金", "担保函"],
            
            # 报价表相关
            "报价表": ["投标报价表", "报价清单", "价格表", "费用清单", "开标一览表"],
            "报价清单": ["报价表", "价格清单", "报价明细"],
            "开标一览表": ["报价一览表", "报价表", "价格一览表"],
            
            # 偏离表相关
            "偏离表": ["技术偏离表", "商务偏离表", "响应偏离表", "技术响应表", "商务响应表"],
            "技术偏离表": ["偏离表", "技术响应表", "技术参数偏离表"],
            "商务偏离表": ["偏离表", "商务响应表", "条款偏离表"],
            
            # 承诺书相关
            "承诺书": ["承诺函", "承诺声明", "保证书"],
            "服务承诺书": ["售后服务承诺书", "服务承诺", "售后承诺"],
            "质量承诺书": ["工期承诺书", "质量及工期承诺书", "履约承诺书"],
            "诚信承诺书": ["廉洁承诺书", "信用承诺书", "廉洁自律承诺书"],
            
            # 声明相关
            "声明函": ["声明书", "承诺函", "资格声明"],
            "无违法记录声明": ["无重大违法记录声明", "信誉声明"],
            
            # 联合体相关
            "联合体协议书": ["联合体协议", "联合体投标协议书", "联合投标协议"],
        }

    
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
        根据归一化标题匹配 FragmentType（原有方法，保持向后兼容）
        
        Args:
            title_norm: 归一化后的标题
            
        Returns:
            匹配到的 FragmentType，如果没有匹配则返回 None
        """
        ftype, _ = self.match_type_with_confidence(title_norm)
        return ftype
    
    def match_type_with_confidence(self, title_norm: str) -> Tuple[Optional[FragmentType], float]:
        """
        根据归一化标题匹配 FragmentType 并返回置信度（增强版）
        
        Args:
            title_norm: 归一化后的标题
            
        Returns:
            (FragmentType, confidence) 或 (None, 0.0)
            
        置信度说明:
            1.0: 完全匹配（标题完全相同）
            0.9: 包含匹配（标题互相包含）
            0.8: 同义词匹配（通过同义词表匹配）
            0.6-0.8: 模糊匹配（基于编辑距离）
            0.0: 无匹配
        """
        if not title_norm:
            return (None, 0.0)
        
        # 1️⃣ 完全匹配（置信度 1.0）
        for ftype, synonyms in self._dict.items():
            for synonym in synonyms:
                syn_norm = self.normalize(synonym)
                if not syn_norm:
                    continue
                
                if title_norm == syn_norm:
                    return (ftype, 1.0)
        
        # 2️⃣ 包含匹配（置信度 0.9）
        matches_contain: List[Tuple[FragmentType, int, float]] = []
        for ftype, synonyms in self._dict.items():
            for synonym in synonyms:
                syn_norm = self.normalize(synonym)
                if not syn_norm:
                    continue
                
                if syn_norm in title_norm or title_norm in syn_norm:
                    # 越长的匹配越优先
                    matches_contain.append((ftype, len(syn_norm), 0.9))
        
        if matches_contain:
            matches_contain.sort(key=lambda x: x[1], reverse=True)
            return (matches_contain[0][0], matches_contain[0][2])
        
        # 3️⃣ 同义词匹配（置信度 0.8）
        ftype_syn = self._match_by_synonyms(title_norm)
        if ftype_syn:
            return (ftype_syn, 0.8)
        
        # 4️⃣ 模糊匹配（置信度 0.6-0.8）
        ftype_fuzzy, fuzzy_score = self._match_by_fuzzy(title_norm)
        if ftype_fuzzy and fuzzy_score >= 70:
            # 将 fuzzywuzzy 的 70-100 分映射到 0.6-0.8 置信度
            confidence = 0.6 + (fuzzy_score - 70) * 0.2 / 30
            return (ftype_fuzzy, confidence)
        
        return (None, 0.0)
    
    def _match_by_synonyms(self, title_norm: str) -> Optional[FragmentType]:
        """
        通过同义词表匹配
        
        Args:
            title_norm: 归一化后的标题
            
        Returns:
            匹配到的 FragmentType，如果没有匹配则返回 None
        """
        # 检查标题中是否包含同义词字典的key
        for key, synonyms_list in self._synonyms.items():
            key_norm = self.normalize(key)
            if key_norm in title_norm:
                # 找到包含这个key的FragmentType
                for ftype, ftype_synonyms in self._dict.items():
                    for syn in ftype_synonyms:
                        syn_norm = self.normalize(syn)
                        if key_norm == syn_norm or key_norm in syn_norm:
                            return ftype
        
        # 检查标题中是否包含同义词列表中的词
        for key, synonyms_list in self._synonyms.items():
            for synonym in synonyms_list:
                syn_norm = self.normalize(synonym)
                if syn_norm and syn_norm in title_norm:
                    # 找到包含这个synonym的FragmentType
                    for ftype, ftype_synonyms in self._dict.items():
                        for fsyn in ftype_synonyms:
                            fsyn_norm = self.normalize(fsyn)
                            key_norm = self.normalize(key)
                            if key_norm == fsyn_norm or key_norm in fsyn_norm:
                                return ftype
        
        return None
    
    def _match_by_fuzzy(self, title_norm: str) -> Tuple[Optional[FragmentType], int]:
        """
        通过模糊匹配（编辑距离）
        
        Args:
            title_norm: 归一化后的标题
            
        Returns:
            (FragmentType, score) 或 (None, 0)
            score 范围: 0-100
        """
        try:
            from fuzzywuzzy import fuzz
        except ImportError:
            # 如果没有安装 fuzzywuzzy，跳过模糊匹配
            return (None, 0)
        
        best_match: Optional[FragmentType] = None
        best_score = 0
        
        for ftype, synonyms in self._dict.items():
            for synonym in synonyms:
                syn_norm = self.normalize(synonym)
                if not syn_norm:
                    continue
                
                # 使用 token_sort_ratio（对词序不敏感）
                score = fuzz.token_sort_ratio(title_norm, syn_norm)
                if score > best_score:
                    best_score = score
                    best_match = ftype
        
        return (best_match, best_score)
