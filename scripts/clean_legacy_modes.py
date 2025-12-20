#!/usr/bin/env python3
"""
清理 tender_service.py 中的 OLD/SHADOW/PREFER_NEW 代码
只保留 NEW_ONLY 分支
"""
import re
import sys

def clean_extract_method(content: str, method_name: str) -> str:
    """清理extract方法，只保留NEW_ONLY分支"""
    
    # 查找方法定义
    pattern = rf'(def {method_name}\([^)]+\):.*?(?=\n    def |\nclass |\Z))'
    match = re.search(pattern, content, re.DOTALL)
    
    if not match:
        print(f"Warning: Method {method_name} not found")
        return content
    
    method_code = match.group(1)
    method_start = match.start(1)
    method_end = match.end(1)
    
    # 构建简化的方法：只保留NEW_ONLY分支
    simplified = f'''def {method_name}(
        self,
        project_id: str,
        model_id: Optional[str],
        run_id: Optional[str] = None,
        owner_id: Optional[str] = None,
    ):
        """
        SIMPLIFIED: Only NEW_ONLY mode supported.
        OLD/SHADOW/PREFER_NEW modes have been removed.
        """
        # 强制要求 NEW_ONLY 模式
        from app.core.cutover import get_cutover_config
        cutover = get_cutover_config()
        extract_mode = cutover.get_mode("extract", project_id)
        
        if extract_mode.value != "NEW_ONLY":
            raise RuntimeError(
                f"[REMOVED] Legacy tender extraction deleted. "
                f"EXTRACT_MODE={{extract_mode.value}} is no longer supported. "
                f"Set EXTRACT_MODE=NEW_ONLY for {method_name}."
            )
        
        # 只走 NEW_ONLY 路径
        try:
            import asyncio
            from app.works.tender.extract_v2_service import ExtractV2Service
            from app.services.db.postgres import _get_pool
            
            logger.info(f"NEW_ONLY {method_name}: using v2 for project={{project_id}}")
            pool = _get_pool()
            extract_v2 = ExtractV2Service(pool, self.llm)
'''
    
    # 根据方法名添加具体调用
    if method_name == "extract_project_info":
        simplified += '''            
            result = asyncio.run(extract_v2.extract_project_info_v2(
                project_id=project_id,
                model_id=model_id,
                run_id=run_id
            ))
            
            # 写入旧表（保证前端兼容）
            self.dao.upsert_project_info(project_id, result)
            
            # 更新运行状态
            if run_id:
                self.dao.update_run(
                    run_id, "success", progress=1.0,
                    message="ok",
                    result_json={"data": result, "extract_mode_used": "NEW_ONLY"}
                )
            
            logger.info(f"NEW_ONLY {method_name}: v2 succeeded for project={{project_id}}")
            
        except Exception as e:
            error_msg = f"EXTRACT_MODE=NEW_ONLY failed: {{str(e)}}"
            logger.error(f"NEW_ONLY {method_name} failed: {{e}}", exc_info=True)
            
            if run_id:
                self.dao.update_run(
                    run_id, "failed", progress=0.0,
                    message=error_msg,
                    result_json={"extract_mode_used": "NEW_ONLY", "error": str(e)}
                )
            
            raise ValueError(error_msg) from e
'''
    elif method_name == "extract_risks":
        simplified += '''            
            v2_result = asyncio.run(extract_v2.extract_risks_v2(
                project_id=project_id,
                model_id=model_id,
                run_id=run_id
            ))
            
            if not isinstance(v2_result, list):
                raise ValueError("v2 risk output not list")
            
            # 写入旧表（保证前端兼容）
            self.dao.replace_risks(project_id, v2_result)
            
            # 更新运行状态
            if run_id:
                self.dao.update_run(
                    run_id, "success", progress=1.0,
                    message="ok",
                    result_json={"risks": v2_result, "extract_mode_used": "NEW_ONLY"}
                )
            
            logger.info(f"NEW_ONLY {method_name}: v2 succeeded, count={{len(v2_result)}}")
            
        except Exception as e:
            error_msg = f"EXTRACT_MODE=NEW_ONLY failed: {{str(e)}}"
            logger.error(f"NEW_ONLY {method_name} failed: {{e}}", exc_info=True)
            
            if run_id:
                self.dao.update_run(
                    run_id, "failed", progress=0.0,
                    message=error_msg,
                    result_json={"extract_mode_used": "NEW_ONLY", "error": str(e)}
                )
            
            raise ValueError(error_msg) from e
'''
    
    # 替换方法
    new_content = content[:method_start] + simplified + content[method_end:]
    return new_content


def main():
    file_path = sys.argv[1] if len(sys.argv) > 1 else "backend/app/services/tender_service.py"
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"Original file size: {len(content)} bytes")
    
    # 清理各个方法
    content = clean_extract_method(content, "extract_project_info")
    content = clean_extract_method(content, "extract_risks")
    
    print(f"Cleaned file size: {len(content)} bytes")
    print(f"Removed: {len(sys.argv[1] if len(sys.argv) > 1 else content) - len(content)} bytes")
    
    # 写回文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"✓ Cleaned {file_path}")


if __name__ == "__main__":
    main()

