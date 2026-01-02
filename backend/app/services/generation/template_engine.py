"""
简单的模板引擎
支持变量替换和条件渲染
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional
from pathlib import Path


class TemplateEngine:
    """
    简单的模板引擎
    
    支持的语法：
    - {{variable}}：变量替换
    - {{#if condition}}...{{else}}...{{/if}}：条件渲染
    """
    
    def __init__(self, template_dir: Optional[str] = None):
        """
        初始化模板引擎
        
        Args:
            template_dir: 模板文件目录
        """
        if template_dir:
            self.template_dir = Path(template_dir)
        else:
            # 默认为当前文件所在目录下的prompts文件夹
            self.template_dir = Path(__file__).parent / "prompts"
    
    def load_template(self, template_name: str) -> str:
        """
        加载模板文件
        
        Args:
            template_name: 模板文件名（相对于template_dir）
            
        Returns:
            模板内容
        """
        template_path = self.template_dir / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Template not found: {template_path}")
        
        return template_path.read_text(encoding="utf-8")
    
    def render(self, template: str, context: Dict[str, Any]) -> str:
        """
        渲染模板
        
        Args:
            template: 模板字符串
            context: 上下文变量
            
        Returns:
            渲染后的字符串
        """
        # Step 1: 处理条件渲染 {{#if}}...{{/if}}
        result = self._render_conditionals(template, context)
        
        # Step 2: 替换变量 {{variable}}
        result = self._replace_variables(result, context)
        
        return result
    
    def render_file(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        加载并渲染模板文件
        
        Args:
            template_name: 模板文件名
            context: 上下文变量
            
        Returns:
            渲染后的字符串
        """
        template = self.load_template(template_name)
        return self.render(template, context)
    
    def _render_conditionals(self, template: str, context: Dict[str, Any]) -> str:
        """处理条件渲染"""
        # 匹配 {{#if condition}}...{{else}}...{{/if}} 或 {{#if condition}}...{{/if}}
        pattern = r'\{\{#if\s+(\w+)\}\}(.*?)(?:\{\{else\}\}(.*?))?\{\{/if\}\}'
        
        def replace_conditional(match):
            condition_var = match.group(1)
            if_block = match.group(2)
            else_block = match.group(3) or ""
            
            # 评估条件
            condition_value = context.get(condition_var, False)
            if self._is_truthy(condition_value):
                return if_block
            else:
                return else_block
        
        # 使用 DOTALL 标志使 .* 匹配包括换行符在内的所有字符
        result = re.sub(pattern, replace_conditional, template, flags=re.DOTALL)
        
        return result
    
    def _replace_variables(self, template: str, context: Dict[str, Any]) -> str:
        """替换变量"""
        # 匹配 {{variable}}
        pattern = r'\{\{(\w+)\}\}'
        
        def replace_variable(match):
            var_name = match.group(1)
            value = context.get(var_name, "")
            
            # 如果值是None或空字符串，返回空
            if value is None:
                return ""
            
            return str(value)
        
        result = re.sub(pattern, replace_variable, template)
        
        return result
    
    def _is_truthy(self, value: Any) -> bool:
        """判断值是否为真"""
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if value is None:
            return False
        # 列表、字典等：非空即为真
        return bool(value)


# 全局模板引擎实例
_template_engine = None


def get_template_engine() -> TemplateEngine:
    """获取全局模板引擎实例"""
    global _template_engine
    if _template_engine is None:
        _template_engine = TemplateEngine()
    return _template_engine

