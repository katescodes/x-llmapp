"""
ASR配置管理服务
"""
import uuid
import json
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status

from app.services.db.postgres import get_conn
from app.services.asr_api_service import test_asr_api

def generate_config_id() -> str:
    """生成配置ID"""
    return f"asr_{uuid.uuid4().hex[:12]}"

def get_all_configs() -> List[Dict[str, Any]]:
    """获取所有ASR配置"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, api_url, api_key, model_name, response_format,
                       is_active, is_default, extra_params, usage_count,
                       last_test_at, last_test_status, last_test_message,
                       created_at, updated_at
                FROM asr_configs
                ORDER BY is_default DESC, created_at DESC
            """)
            
            rows = cur.fetchall()
            return [
                {
                    "id": row['id'],
                    "name": row['name'],
                    "api_url": row['api_url'],
                    "api_key": "***" if row.get('api_key') else None,  # 隐藏API密钥
                    "model_name": row['model_name'],
                    "response_format": row['response_format'],
                    "is_active": row['is_active'],
                    "is_default": row['is_default'],
                    "extra_params": row.get('extra_params') or {},
                    "usage_count": row['usage_count'],
                    "last_test_at": row['last_test_at'].isoformat() if row.get('last_test_at') else None,
                    "last_test_status": row['last_test_status'],
                    "last_test_message": row['last_test_message'],
                    "created_at": row['created_at'].isoformat() if row.get('created_at') else None,
                    "updated_at": row['updated_at'].isoformat() if row.get('updated_at') else None,
                }
                for row in rows
            ]

def get_config_by_id(config_id: str) -> Optional[Dict[str, Any]]:
    """获取指定配置"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, api_url, api_key, model_name, response_format,
                       is_active, is_default, extra_params, usage_count,
                       last_test_at, last_test_status, last_test_message,
                       created_at, updated_at
                FROM asr_configs
                WHERE id = %s
            """, (config_id,))
            
            row = cur.fetchone()
            if not row:
                return None
            
            return {
                "id": row['id'],
                "name": row['name'],
                "api_url": row['api_url'],
                "api_key": row['api_key'],  # 完整API密钥
                "model_name": row['model_name'],
                "response_format": row['response_format'],
                "is_active": row['is_active'],
                "is_default": row['is_default'],
                "extra_params": row.get('extra_params') or {},
                "usage_count": row['usage_count'],
                "last_test_at": row['last_test_at'].isoformat() if row.get('last_test_at') else None,
                "last_test_status": row['last_test_status'],
                "last_test_message": row['last_test_message'],
                "created_at": row['created_at'].isoformat() if row.get('created_at') else None,
                "updated_at": row['updated_at'].isoformat() if row.get('updated_at') else None,
            }

def create_config(
    name: str,
    api_url: str,
    model_name: str = "whisper",
    response_format: str = "verbose_json",
    api_key: Optional[str] = None,
    is_active: bool = True,
    is_default: bool = False,
    extra_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """创建新配置"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            config_id = generate_config_id()
            
            cur.execute("""
                INSERT INTO asr_configs (
                    id, name, api_url, api_key, model_name, response_format,
                    is_active, is_default, extra_params
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                RETURNING id, name, api_url, model_name, response_format,
                          is_active, is_default, extra_params, usage_count,
                          created_at, updated_at
            """, (
                config_id, name, api_url, api_key, model_name, response_format,
                is_active, is_default, json.dumps(extra_params or {})
            ))
            
            row = cur.fetchone()
            conn.commit()
            
            return {
                "id": row['id'],
                "name": row['name'],
                "api_url": row['api_url'],
                "model_name": row['model_name'],
                "response_format": row['response_format'],
                "is_active": row['is_active'],
                "is_default": row['is_default'],
                "extra_params": row.get('extra_params') or {},
                "usage_count": row['usage_count'],
                "created_at": row['created_at'].isoformat() if row.get('created_at') else None,
                "updated_at": row['updated_at'].isoformat() if row.get('updated_at') else None,
            }

def update_config(
    config_id: str,
    name: Optional[str] = None,
    api_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    response_format: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_default: Optional[bool] = None,
    extra_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """更新配置"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 构建更新语句
            update_fields = []
            params = []
            
            if name is not None:
                update_fields.append("name = %s")
                params.append(name)
            if api_url is not None:
                update_fields.append("api_url = %s")
                params.append(api_url)
            if api_key is not None:
                update_fields.append("api_key = %s")
                params.append(api_key)
            if model_name is not None:
                update_fields.append("model_name = %s")
                params.append(model_name)
            if response_format is not None:
                update_fields.append("response_format = %s")
                params.append(response_format)
            if is_active is not None:
                update_fields.append("is_active = %s")
                params.append(is_active)
            if is_default is not None:
                update_fields.append("is_default = %s")
                params.append(is_default)
            if extra_params is not None:
                update_fields.append("extra_params = %s::jsonb")
                params.append(json.dumps(extra_params))
            
            if not update_fields:
                config = get_config_by_id(config_id)
                if not config:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Configuration not found"
                    )
                return config
            
            # updated_at 由数据库触发器自动更新，不需要手动设置
            params.append(config_id)
            
            query = f"""
                UPDATE asr_configs
                SET {', '.join(update_fields)}
                WHERE id = %s
                RETURNING id
            """
            
            cur.execute(query, params)
            result = cur.fetchone()
            
            if not result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Configuration not found"
                )
            
            conn.commit()
            
            return get_config_by_id(config_id)

def delete_config(config_id: str) -> bool:
    """删除配置"""
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查是否为默认配置
            cur.execute(
                "SELECT is_default FROM asr_configs WHERE id = %s",
                (config_id,)
            )
            row = cur.fetchone()
            
            if not row:
                return False
            
            if row['is_default']:  # is_default
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot delete default configuration. Set another config as default first."
                )
            
            cur.execute("DELETE FROM asr_configs WHERE id = %s", (config_id,))
            deleted = cur.rowcount > 0
            conn.commit()
            
            return deleted

async def test_config(config_id: str) -> Dict[str, Any]:
    """测试配置"""
    config = get_config_by_id(config_id)
    
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found"
        )
    
    # 调用测试函数
    test_result = await test_asr_api(
        api_url=config['api_url'],
        model_name=config['model_name'],
        response_format=config['response_format'],
        api_key=config.get('api_key'),
        extra_params=config.get('extra_params', {})
    )
    
    # 更新测试结果到数据库
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE asr_configs
                SET 
                    last_test_at = CURRENT_TIMESTAMP,
                    last_test_status = %s,
                    last_test_message = %s
                WHERE id = %s
            """, (
                'success' if test_result['success'] else 'failed',
                test_result['message'],
                config_id
            ))
            conn.commit()
    
    return test_result

def import_from_curl(curl_command: str) -> Dict[str, Any]:
    """从curl命令导入配置"""
    import re
    
    # 解析curl命令
    # 示例: curl --location --request POST 'https://ai.yglinker.com:6399/v1/audio/transcriptions' --form 'model="whisper"' --form 'response_format="verbose_json"'
    
    try:
        # 提取URL
        url_match = re.search(r"(?:POST|GET)\s+'([^']+)'", curl_command)
        if not url_match:
            url_match = re.search(r'(?:POST|GET)\s+"([^"]+)"', curl_command)
        if not url_match:
            url_match = re.search(r'(?:POST|GET)\s+(\S+)', curl_command)
        
        if not url_match:
            raise ValueError("无法从curl命令中提取URL")
        
        api_url = url_match.group(1)
        
        # 提取model
        model_match = re.search(r"--form\s+'model=\"([^\"]+)\"'", curl_command)
        if not model_match:
            model_match = re.search(r'--form\s+"model=\\"([^\\"]+)\\""', curl_command)
        model_name = model_match.group(1) if model_match else "whisper"
        
        # 提取response_format
        format_match = re.search(r"--form\s+'response_format=\"([^\"]+)\"'", curl_command)
        if not format_match:
            format_match = re.search(r'--form\s+"response_format=\\"([^\\"]+)\\""', curl_command)
        response_format = format_match.group(1) if format_match else "verbose_json"
        
        # 提取Authorization header (如果有)
        auth_match = re.search(r"--header\s+'Authorization:\s*Bearer\s+([^']+)'", curl_command)
        if not auth_match:
            auth_match = re.search(r'--header\s+"Authorization:\s*Bearer\s+([^"]+)"', curl_command)
        api_key = auth_match.group(1) if auth_match else None
        
        # 生成配置名称
        from urllib.parse import urlparse
        parsed_url = urlparse(api_url)
        name = f"从curl导入 - {parsed_url.netloc}"
        
        # 创建配置
        return create_config(
            name=name,
            api_url=api_url,
            model_name=model_name,
            response_format=response_format,
            api_key=api_key,
            is_active=True,
            is_default=False
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"解析curl命令失败: {str(e)}"
        )
