"""
Prompt加载服务
负责从数据库加载最新的Prompt模板，替代原来的文件读取方式
"""
from typing import Optional
import logging
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class PromptLoaderService:
    """Prompt加载服务"""
    
    def __init__(self, pool):
        self.pool = pool
    
    async def get_active_prompt(self, module: str) -> Optional[str]:
        """
        获取指定模块的激活Prompt
        
        Args:
            module: 模块名称（project_info, risks, directory, review）
        
        Returns:
            Prompt内容（Markdown格式），如果不存在则返回None
        """
        query = """
            SELECT content 
            FROM prompt_templates 
            WHERE module = %s AND is_active = TRUE 
            ORDER BY version DESC 
            LIMIT 1
        """
        
        try:
            with self.pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, (module,))
                    row = cur.fetchone()
        
            if row:
                content = row["content"]
                logger.info(f"✅ [PromptLoader] Loaded prompt for module '{module}' from DATABASE, length={len(content)}")
                print(f"✅ [PromptLoader] Loaded prompt for module '{module}' from DATABASE, length={len(content)}")
                return content
            else:
                logger.warning(f"⚠️ [PromptLoader] No active prompt found for module '{module}' in database")
                print(f"⚠️ [PromptLoader] No active prompt found for module '{module}' in database")
                return None
        except Exception as e:
            logger.error(f"❌ [PromptLoader] Error loading prompt for module '{module}': {e}", exc_info=True)
            print(f"❌ [PromptLoader] Error loading prompt for module '{module}': {e}")
            return None
    
    async def get_prompt_by_id(self, prompt_id: str) -> Optional[str]:
        """
        通过ID获取Prompt
        
        Args:
            prompt_id: Prompt模板ID
        
        Returns:
            Prompt内容
        """
        query = "SELECT content FROM prompt_templates WHERE id = %s"
        
        try:
            with self.pool.connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, (prompt_id,))
                    row = cur.fetchone()
            
            if row:
                return row["content"]
            return None
        except Exception as e:
            logger.error(f"Error loading prompt by id '{prompt_id}': {e}")
            return None
    
    async def get_prompt_with_fallback(self, module: str, fallback_content: str) -> str:
        """
        获取Prompt，如果数据库中没有则使用fallback
        
        Args:
            module: 模块名称
            fallback_content: 备用内容（从文件读取的原始Prompt）
        
        Returns:
            Prompt内容
        """
        db_prompt = await self.get_active_prompt(module)
        if db_prompt:
            logger.info(f"📊 [PromptLoader] Using DATABASE prompt for module '{module}'")
            print(f"📊 [PromptLoader] Using DATABASE prompt for module '{module}'")
            return db_prompt
        else:
            logger.info(f"📁 [PromptLoader] Using FALLBACK prompt for module '{module}'")
            print(f"📁 [PromptLoader] Using FALLBACK prompt for module '{module}'")
            return fallback_content


