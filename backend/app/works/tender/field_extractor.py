"""
TenderFieldExtractor - 招标书关键字段提取器
从招标书全文中提取关键信息（采购人、项目名称、编号、时间、金额等）
"""
import re
from typing import Dict, Optional, List, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class TenderFieldExtractor:
    """招标书字段提取器 - 基于规则引擎"""
    
    def __init__(self):
        """初始化提取规则"""
        self.rules = self._build_extraction_rules()
    
    def _build_extraction_rules(self) -> Dict[str, List[dict]]:
        """
        构建字段提取规则
        
        返回格式：
        {
            "field_name": [
                {
                    "pattern": r"正则表达式",
                    "group": 1,  # 提取第几个捕获组
                    "weight": 10,  # 权重（位置、可信度）
                    "validator": lambda x: len(x) > 0  # 验证函数
                },
                ...
            ]
        }
        """
        return {
            # 1. 采购人/招标人名称
            "purchaser_name": [
                {"pattern": r"采购人[：:\s]*([^\n：:]{2,50}?)(?:\s|$|；)", "group": 1, "weight": 10},
                {"pattern": r"招标人[：:\s]*([^\n：:]{2,50}?)(?:\s|$|；)", "group": 1, "weight": 10},
                {"pattern": r"甲方[：:\s]*([^\n：:]{2,50}?)(?:\s|$|；)", "group": 1, "weight": 8},
                {"pattern": r"采购单位[：:\s]*([^\n：:]{2,50}?)(?:\s|$|；)", "group": 1, "weight": 9},
                {"pattern": r"招标单位[：:\s]*([^\n：:]{2,50}?)(?:\s|$|；)", "group": 1, "weight": 9},
            ],
            
            # 2. 项目名称
            "project_name": [
                {"pattern": r"项目名称[：:\s]*([^\n：:]{5,100}?)(?:\s|$|招标|采购)", "group": 1, "weight": 10},
                {"pattern": r"工程名称[：:\s]*([^\n：:]{5,100}?)(?:\s|$|招标|采购)", "group": 1, "weight": 10},
                {"pattern": r"([^\n]{5,80}?)(?:招标文件|采购文件|竞争性磋商文件)", "group": 1, "weight": 7},
                {"pattern": r"^([^\n]{5,80}?)项目$", "group": 1, "weight": 6},
            ],
            
            # 3. 招标编号/项目编号
            "project_number": [
                {"pattern": r"招标编号[：:\s]*([A-Z0-9\-/]{5,30})", "group": 1, "weight": 10},
                {"pattern": r"项目编号[：:\s]*([A-Z0-9\-/]{5,30})", "group": 1, "weight": 10},
                {"pattern": r"采购编号[：:\s]*([A-Z0-9\-/]{5,30})", "group": 1, "weight": 10},
                {"pattern": r"磋商编号[：:\s]*([A-Z0-9\-/]{5,30})", "group": 1, "weight": 10},
                {"pattern": r"编号[：:\s]*([A-Z0-9\-/]{5,30})", "group": 1, "weight": 7},
            ],
            
            # 4. 开标时间
            "bid_opening_time": [
                {"pattern": r"开标时间[：:\s]*(\d{4}年\d{1,2}月\d{1,2}日(?:\s*\d{1,2}[:：]\d{1,2})?)", "group": 1, "weight": 10},
                {"pattern": r"开标时间[：:\s]*(\d{4}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{1,2})?)", "group": 1, "weight": 10},
                {"pattern": r"开标日期[：:\s]*(\d{4}年\d{1,2}月\d{1,2}日)", "group": 1, "weight": 9},
                {"pattern": r"(\d{4}年\d{1,2}月\d{1,2}日(?:\s*\d{1,2}[:：]\d{1,2}))开标", "group": 1, "weight": 8},
            ],
            
            # 5. 投标截止时间
            "bid_deadline": [
                {"pattern": r"投标截止时间[：:\s]*(\d{4}年\d{1,2}月\d{1,2}日(?:\s*\d{1,2}[:：]\d{1,2})?)", "group": 1, "weight": 10},
                {"pattern": r"投标截止时间[：:\s]*(\d{4}-\d{1,2}-\d{1,2}(?:\s+\d{1,2}:\d{1,2})?)", "group": 1, "weight": 10},
                {"pattern": r"递交投标文件截止时间[：:\s]*(\d{4}年\d{1,2}月\d{1,2}日(?:\s*\d{1,2}[:：]\d{1,2})?)", "group": 1, "weight": 9},
            ],
            
            # 6. 预算金额/最高限价
            "budget_amount": [
                {"pattern": r"预算金额[：:\s]*([\d,，\.]+(?:万元|元))", "group": 1, "weight": 10},
                {"pattern": r"最高限价[：:\s]*([\d,，\.]+(?:万元|元))", "group": 1, "weight": 10},
                {"pattern": r"控制价[：:\s]*([\d,，\.]+(?:万元|元))", "group": 1, "weight": 9},
                {"pattern": r"投资估算[：:\s]*([\d,，\.]+(?:万元|元))", "group": 1, "weight": 8},
                {"pattern": r"项目预算[：:\s]*([\d,，\.]+(?:万元|元))", "group": 1, "weight": 8},
            ],
            
            # 7. 投标保证金
            "bid_bond": [
                {"pattern": r"投标保证金[：:\s]*([\d,，\.]+(?:万元|元))", "group": 1, "weight": 10},
                {"pattern": r"保证金[：:\s]*([\d,，\.]+(?:万元|元))", "group": 1, "weight": 8},
            ],
            
            # 8. 联系人
            "contact_person": [
                {"pattern": r"联系人[：:\s]*([^\n：:]{2,10}?)(?:\s|$|联系电话|电话)", "group": 1, "weight": 10},
                {"pattern": r"项目联系人[：:\s]*([^\n：:]{2,10}?)(?:\s|$|联系电话|电话)", "group": 1, "weight": 9},
            ],
            
            # 9. 联系电话
            "contact_phone": [
                {"pattern": r"联系电话[：:\s]*([\d\-]{7,20})", "group": 1, "weight": 10},
                {"pattern": r"电话[：:\s]*([\d\-]{7,20})", "group": 1, "weight": 8},
                {"pattern": r"联系方式[：:\s]*([\d\-]{7,20})", "group": 1, "weight": 9},
            ],
            
            # 10. 代理机构
            "agent_name": [
                {"pattern": r"代理机构[：:\s]*([^\n：:]{2,50}?)(?:\s|$|；)", "group": 1, "weight": 10},
                {"pattern": r"招标代理[：:\s]*([^\n：:]{2,50}?)(?:\s|$|；)", "group": 1, "weight": 9},
                {"pattern": r"采购代理[：:\s]*([^\n：:]{2,50}?)(?:\s|$|；)", "group": 1, "weight": 9},
            ],
        }
    
    def extract_from_text(self, full_text: str) -> Dict[str, Optional[str]]:
        """
        从全文中提取所有关键字段
        
        Args:
            full_text: 招标书完整文本
            
        Returns:
            {
                "purchaser_name": "某某公司",
                "project_name": "某某项目",
                "project_number": "2024-001",
                ...
            }
        """
        if not full_text or len(full_text) < 10:
            logger.warning("文本内容为空或过短，无法提取字段")
            return {}
        
        results = {}
        
        # 对每个字段应用规则
        for field_name, rules in self.rules.items():
            extracted_value = self._extract_field(full_text, field_name, rules)
            results[field_name] = extracted_value
            
            if extracted_value:
                logger.info(f"✅ 提取字段 [{field_name}]: {extracted_value}")
            else:
                logger.debug(f"⚠️  未提取到字段 [{field_name}]")
        
        return results
    
    def _extract_field(
        self, 
        text: str, 
        field_name: str, 
        rules: List[dict]
    ) -> Optional[str]:
        """
        提取单个字段（应用多条规则，选择最可信的）
        
        Args:
            text: 文本
            field_name: 字段名
            rules: 规则列表
            
        Returns:
            提取的字段值
        """
        candidates: List[Tuple[str, int]] = []  # (value, weight)
        
        for rule in rules:
            pattern = rule["pattern"]
            group = rule.get("group", 1)
            weight = rule.get("weight", 5)
            
            try:
                matches = re.finditer(pattern, text, re.MULTILINE)
                for match in matches:
                    value = match.group(group).strip()
                    
                    # 清理提取的值
                    value = self._clean_value(value, field_name)
                    
                    # 验证
                    if self._validate_value(value, field_name):
                        # 位置权重：前1000字符权重+2，前5000字符权重+1
                        position_bonus = 0
                        if match.start() < 1000:
                            position_bonus = 2
                        elif match.start() < 5000:
                            position_bonus = 1
                        
                        candidates.append((value, weight + position_bonus))
            
            except re.error as e:
                logger.warning(f"正则表达式错误 [{field_name}]: {e}")
                continue
        
        if not candidates:
            return None
        
        # 按权重排序，选择最高权重的
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        # 如果最高权重的有多个，选择最长的（更完整）
        top_weight = candidates[0][1]
        top_candidates = [c[0] for c in candidates if c[1] == top_weight]
        
        return max(top_candidates, key=len)
    
    def _clean_value(self, value: str, field_name: str) -> str:
        """清理提取的值"""
        # 移除首尾空白
        value = value.strip()
        
        # 移除常见的尾部干扰词
        noise_suffixes = ['招标', '采购', '文件', '的', '为', '是']
        for suffix in noise_suffixes:
            if value.endswith(suffix):
                value = value[:-len(suffix)].strip()
        
        # 移除首尾标点
        value = value.strip('：:，,。.；;、 ')
        
        return value
    
    def _validate_value(self, value: str, field_name: str) -> bool:
        """验证提取的值是否合理"""
        if not value or len(value) < 2:
            return False
        
        # 字段特定验证
        if field_name == "project_number":
            # 编号应该包含字母或数字
            if not re.search(r'[A-Z0-9]', value):
                return False
        
        elif field_name in ["bid_opening_time", "bid_deadline"]:
            # 时间格式验证
            if not re.search(r'\d{4}', value):  # 至少包含年份
                return False
        
        elif field_name in ["budget_amount", "bid_bond"]:
            # 金额验证
            if not re.search(r'\d', value):
                return False
        
        elif field_name == "contact_phone":
            # 电话号码验证（至少7位数字）
            digits = re.findall(r'\d', value)
            if len(digits) < 7:
                return False
        
        elif field_name in ["purchaser_name", "agent_name"]:
            # 名称不应该太短或包含奇怪字符
            if len(value) < 3 or len(value) > 50:
                return False
        
        return True
    
    def extract_from_project(self, project_id: str) -> Dict[str, Optional[str]]:
        """
        从项目的知识库文档中提取字段
        
        Args:
            project_id: 项目ID
            
        Returns:
            提取的字段字典
        """
        try:
            from app.services.dao.tender_dao import TenderDAO
            from app.services.db.postgres import _get_pool
            
            pool = _get_pool()
            dao = TenderDAO(pool)
            
            # 获取项目关联的知识库
            project = dao.get_project(project_id)
            if not project:
                logger.error(f"项目不存在: {project_id}")
                return {}
            
            kb_id = project.get("kb_id")
            if not kb_id:
                logger.warning(f"项目 {project_id} 未关联知识库")
                return {}
            
            # 从知识库中获取所有文档的文本
            from app.services.kb_service import KBService
            kb_service = KBService()
            
            # 获取文档列表
            docs = kb_service.list_documents(kb_id)
            
            # 合并所有文档的文本
            full_text_parts = []
            for doc in docs[:5]:  # 只取前5个文档（避免过大）
                doc_id = doc.get("id")
                if doc_id:
                    # 获取文档的所有片段
                    from app.services.docstore_service import DocStoreService
                    ds = DocStoreService()
                    
                    # 获取文档最新版本的文本
                    version = ds.get_latest_version(doc_id)
                    if version:
                        segments = ds.list_segments(version["id"])
                        for seg in segments[:100]:  # 每个文档最多100个片段
                            if seg.get("text"):
                                full_text_parts.append(seg["text"])
            
            if not full_text_parts:
                logger.warning(f"知识库 {kb_id} 中没有可用的文本内容")
                return {}
            
            full_text = "\n".join(full_text_parts)
            logger.info(f"从知识库提取文本，总长度: {len(full_text)} 字符")
            
            # 提取字段
            return self.extract_from_text(full_text)
        
        except Exception as e:
            logger.error(f"从项目提取字段失败: {e}", exc_info=True)
            return {}


# 字段名称映射（中文显示）
FIELD_DISPLAY_NAMES = {
    "purchaser_name": "采购人名称",
    "project_name": "项目名称",
    "project_number": "项目编号",
    "bid_opening_time": "开标时间",
    "bid_deadline": "投标截止时间",
    "budget_amount": "预算金额",
    "bid_bond": "投标保证金",
    "contact_person": "联系人",
    "contact_phone": "联系电话",
    "agent_name": "代理机构",
}

