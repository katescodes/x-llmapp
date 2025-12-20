"""
HtmlToDocxInserter - HTML转Word文档插入器
用于将用户编辑的HTML内容插入到Word文档中
"""
import re
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


class HtmlToDocxInserter:
    """HTML转Word文档插入器"""
    
    @staticmethod
    def insert(dest_doc: Document, html_content: str):
        """
        将HTML内容插入到目标文档
        
        Args:
            dest_doc: 目标Document对象
            html_content: HTML内容字符串
        """
        if not html_content:
            return
        
        # 简单的HTML解析（最小可用版本）
        # 支持: <p>, <br>, <b>/<strong>, <i>/<em>, <ul>/<ol>/<li>
        
        # 移除HTML标签外的多余空白
        html_content = html_content.strip()
        
        # 分割成段落（按 <p> 标签）
        paragraphs = re.split(r'<p[^>]*>|</p>', html_content)
        
        for para_html in paragraphs:
            para_html = para_html.strip()
            if not para_html:
                continue
            
            # 检查是否是列表项
            if '<li>' in para_html or '<ul>' in para_html or '<ol>' in para_html:
                HtmlToDocxInserter._insert_list(dest_doc, para_html)
            else:
                HtmlToDocxInserter._insert_paragraph(dest_doc, para_html)
    
    @staticmethod
    def _insert_paragraph(dest_doc: Document, para_html: str):
        """插入一个段落"""
        para = dest_doc.add_paragraph()
        
        # 处理换行符 <br>
        segments = re.split(r'<br\s*/?>', para_html)
        
        for i, segment in enumerate(segments):
            if i > 0:
                # 添加换行
                para.add_run('\n')
            
            HtmlToDocxInserter._insert_runs(para, segment)
    
    @staticmethod
    def _insert_runs(para, html_segment: str):
        """解析HTML片段并插入runs"""
        # 简单状态机解析
        text = ""
        bold = False
        italic = False
        underline = False
        
        i = 0
        while i < len(html_segment):
            # 检查标签
            if html_segment[i] == '<':
                # 保存当前文本
                if text:
                    run = para.add_run(text)
                    run.bold = bold
                    run.italic = italic
                    run.underline = underline
                    text = ""
                
                # 查找标签结束
                tag_end = html_segment.find('>', i)
                if tag_end == -1:
                    break
                
                tag = html_segment[i:tag_end+1].lower()
                
                # 解析标签
                if tag in ('<b>', '<strong>'):
                    bold = True
                elif tag in ('</b>', '</strong>'):
                    bold = False
                elif tag in ('<i>', '<em>'):
                    italic = True
                elif tag in ('</i>', '</em>'):
                    italic = False
                elif tag in ('<u>',):
                    underline = True
                elif tag in ('</u>',):
                    underline = False
                
                i = tag_end + 1
            else:
                # 普通字符
                text += html_segment[i]
                i += 1
        
        # 插入剩余文本
        if text:
            # 解码HTML实体
            text = HtmlToDocxInserter._decode_html_entities(text)
            run = para.add_run(text)
            run.bold = bold
            run.italic = italic
            run.underline = underline
    
    @staticmethod
    def _insert_list(dest_doc: Document, list_html: str):
        """插入列表"""
        # 提取列表项
        items = re.findall(r'<li[^>]*>(.*?)</li>', list_html, re.DOTALL)
        
        # 判断是有序还是无序
        is_ordered = '<ol' in list_html.lower()
        
        for i, item_html in enumerate(items):
            item_html = item_html.strip()
            if not item_html:
                continue
            
            # 移除内层HTML标签（简化处理）
            item_text = re.sub(r'<[^>]+>', '', item_html)
            item_text = HtmlToDocxInserter._decode_html_entities(item_text)
            
            # 添加前缀
            if is_ordered:
                prefix = f"{i+1}. "
            else:
                prefix = "• "
            
            para = dest_doc.add_paragraph()
            para.add_run(prefix + item_text)
    
    @staticmethod
    def _decode_html_entities(text: str) -> str:
        """解码HTML实体"""
        replacements = {
            '&nbsp;': ' ',
            '&lt;': '<',
            '&gt;': '>',
            '&amp;': '&',
            '&quot;': '"',
            '&#39;': "'",
        }
        for entity, char in replacements.items():
            text = text.replace(entity, char)
        return text
