#!/usr/bin/env python3
"""
ASR接口调试脚本
用于测试和诊断ASR转写功能问题
"""
import sys
import os
import asyncio
import logging

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.asr_api_service import call_remote_asr_api, test_asr_api
from app.services.db.postgres import get_conn
from pathlib import Path
import tempfile
import struct
import wave

# 设置日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_audio():
    """创建测试音频文件（1秒静音）"""
    sample_rate = 16000
    duration_sec = 1
    num_samples = sample_rate * duration_sec
    
    # 生成静音音频数据
    audio_data = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))
    
    # 写入临时WAV文件
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_path = Path(temp_file.name)
    
    with wave.open(str(temp_path), 'wb') as wav_file:
        wav_file.setnchannels(1)  # 单声道
        wav_file.setsampwidth(2)  # 16位
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data)
    
    logger.info(f"✅ 创建测试音频: {temp_path}")
    return temp_path

def check_database_config():
    """检查数据库中的ASR配置"""
    logger.info("\n" + "="*60)
    logger.info("1. 检查数据库ASR配置")
    logger.info("="*60)
    
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # 查询所有配置
                cur.execute("""
                    SELECT id, name, api_url, model_name, response_format, 
                           is_active, is_default, extra_params,
                           last_test_status, last_test_message
                    FROM asr_configs
                    ORDER BY is_default DESC, created_at
                """)
                configs = cur.fetchall()
                
                if not configs:
                    logger.error("❌ 数据库中没有ASR配置！")
                    logger.info("\n解决方法：")
                    logger.info("1. 运行迁移脚本: python backend/scripts/run_migrations.py")
                    logger.info("2. 或手动插入配置:")
                    logger.info("""
INSERT INTO asr_configs (id, name, api_url, model_name, response_format, is_active, is_default)
VALUES (
    'asr-default-001',
    '默认语音转文本API',
    'https://ai.yglinker.com:6399/v1/audio/transcriptions',
    'whisper',
    'verbose_json',
    TRUE,
    TRUE
);
                    """)
                    return None
                
                logger.info(f"✅ 找到 {len(configs)} 个ASR配置:\n")
                
                for config in configs:
                    logger.info(f"配置 ID: {config['id']}")
                    logger.info(f"  名称: {config['name']}")
                    logger.info(f"  API地址: {config['api_url']}")
                    logger.info(f"  模型: {config['model_name']}")
                    logger.info(f"  响应格式: {config['response_format']}")
                    logger.info(f"  激活状态: {'✅' if config['is_active'] else '❌'}")
                    logger.info(f"  默认配置: {'✅' if config['is_default'] else '❌'}")
                    logger.info(f"  额外参数: {config.get('extra_params', {})}")
                    
                    if config['last_test_status']:
                        status_icon = '✅' if config['last_test_status'] == 'success' else '❌'
                        logger.info(f"  上次测试: {status_icon} {config['last_test_message']}")
                    
                    logger.info("")
                
                # 返回默认配置
                default_config = next((c for c in configs if c['is_default']), configs[0])
                logger.info(f"📌 使用默认配置: {default_config['name']}")
                
                return {
                    'api_url': default_config['api_url'],
                    'api_key': default_config.get('api_key'),
                    'model_name': default_config.get('model_name') or 'whisper',
                    'response_format': default_config.get('response_format') or 'verbose_json',
                    'extra_params': default_config.get('extra_params') or {}
                }
                
    except Exception as e:
        logger.error(f"❌ 数据库查询失败: {e}")
        logger.exception(e)
        return None

async def test_direct_api_call(config):
    """直接测试API调用"""
    logger.info("\n" + "="*60)
    logger.info("2. 直接测试API调用")
    logger.info("="*60)
    
    if not config:
        logger.error("❌ 没有可用的配置")
        return False
    
    try:
        # 创建测试音频
        test_audio_path = create_test_audio()
        
        try:
            logger.info(f"\n调用ASR API:")
            logger.info(f"  URL: {config['api_url']}")
            logger.info(f"  Model: {config['model_name']}")
            logger.info(f"  Format: {config['response_format']}")
            logger.info(f"  Extra: {config['extra_params']}")
            
            # 调用API
            text, duration = await call_remote_asr_api(
                audio_file_path=test_audio_path,
                api_url=config['api_url'],
                model_name=config['model_name'],
                response_format=config['response_format'],
                api_key=config.get('api_key'),
                extra_params=config['extra_params'],
                timeout=30
            )
            
            logger.info(f"\n✅ API调用成功!")
            logger.info(f"  转写文本: {text[:100] if text else '(空)'}")
            logger.info(f"  音频时长: {duration}秒")
            
            return True
            
        finally:
            # 清理测试文件
            test_audio_path.unlink(missing_ok=True)
            
    except Exception as e:
        logger.error(f"\n❌ API调用失败: {e}")
        logger.exception(e)
        return False

async def test_service_layer(config):
    """测试服务层调用"""
    logger.info("\n" + "="*60)
    logger.info("3. 测试服务层调用")
    logger.info("="*60)
    
    if not config:
        logger.error("❌ 没有可用的配置")
        return False
    
    try:
        from app.services.asr_service import transcribe_audio
        
        # 创建测试音频
        test_audio_path = create_test_audio()
        
        try:
            # 读取音频数据
            with open(test_audio_path, 'rb') as f:
                audio_data = f.read()
            
            logger.info(f"\n调用 transcribe_audio 服务:")
            logger.info(f"  文件名: test.wav")
            logger.info(f"  数据大小: {len(audio_data)} bytes")
            
            # 调用服务
            text, duration = await transcribe_audio(
                audio_data=audio_data,
                filename="test.wav",
                language="zh",
                enhance=False
            )
            
            logger.info(f"\n✅ 服务调用成功!")
            logger.info(f"  转写文本: {text[:100] if text else '(空)'}")
            logger.info(f"  音频时长: {duration}秒")
            
            return True
            
        finally:
            # 清理测试文件
            test_audio_path.unlink(missing_ok=True)
            
    except Exception as e:
        logger.error(f"\n❌ 服务调用失败: {e}")
        logger.exception(e)
        
        # 提供诊断信息
        if "ASR 服务未启用" in str(e):
            logger.info("\n解决方法:")
            logger.info("在 backend/.env 文件中设置: ASR_ENABLED=true")
        elif "未找到可用的ASR API配置" in str(e):
            logger.info("\n解决方法:")
            logger.info("1. 检查数据库中是否有激活的ASR配置")
            logger.info("2. 运行迁移脚本或手动添加配置")
        
        return False

def check_environment():
    """检查环境变量"""
    logger.info("\n" + "="*60)
    logger.info("0. 检查环境变量")
    logger.info("="*60)
    
    from app.config import get_settings
    settings = get_settings()
    
    logger.info(f"ASR_ENABLED: {settings.ASR_ENABLED}")
    logger.info(f"APP_DATA_DIR: {settings.APP_DATA_DIR}")
    
    if not settings.ASR_ENABLED:
        logger.warning("\n⚠️ ASR功能未启用!")
        logger.info("在 backend/.env 文件中设置: ASR_ENABLED=true")

async def test_with_real_audio(config, audio_file_path: str):
    """使用真实音频文件测试"""
    logger.info("\n" + "="*60)
    logger.info("4. 使用真实音频文件测试")
    logger.info("="*60)
    
    if not config:
        logger.error("❌ 没有可用的配置")
        return False
    
    if not audio_file_path or not Path(audio_file_path).exists():
        logger.warning("⚠️ 未提供音频文件或文件不存在，跳过此测试")
        return True
    
    try:
        from app.services.asr_service import transcribe_audio
        
        audio_path = Path(audio_file_path)
        logger.info(f"音频文件: {audio_path}")
        logger.info(f"文件大小: {audio_path.stat().st_size / 1024:.2f} KB")
        
        # 读取音频数据
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        logger.info("\n开始转写...")
        
        # 调用服务
        text, duration = await transcribe_audio(
            audio_data=audio_data,
            filename=audio_path.name,
            language="zh",
            enhance=False
        )
        
        logger.info(f"\n✅ 转写成功!")
        logger.info(f"  音频时长: {duration}秒")
        logger.info(f"  文本长度: {len(text)} 字符")
        logger.info(f"\n转写文本:\n{text[:500]}")
        
        if len(text) > 500:
            logger.info(f"... (还有 {len(text) - 500} 字符)")
        
        return True
        
    except Exception as e:
        logger.error(f"\n❌ 转写失败: {e}")
        logger.exception(e)
        return False

async def main():
    """主函数"""
    logger.info("🔍 ASR接口诊断工具")
    logger.info("="*60)
    
    # 检查环境变量
    check_environment()
    
    # 检查数据库配置
    config = check_database_config()
    
    if not config:
        logger.error("\n❌ 无法获取ASR配置，测试终止")
        return 1
    
    # 直接测试API
    api_result = await test_direct_api_call(config)
    
    # 测试服务层
    service_result = await test_service_layer(config)
    
    # 如果提供了音频文件路径，测试真实音频
    if len(sys.argv) > 1:
        audio_file = sys.argv[1]
        await test_with_real_audio(config, audio_file)
    
    # 总结
    logger.info("\n" + "="*60)
    logger.info("测试总结")
    logger.info("="*60)
    logger.info(f"数据库配置: {'✅' if config else '❌'}")
    logger.info(f"直接API调用: {'✅' if api_result else '❌'}")
    logger.info(f"服务层调用: {'✅' if service_result else '❌'}")
    
    if api_result and service_result:
        logger.info("\n🎉 所有测试通过! ASR功能正常")
        return 0
    else:
        logger.error("\n❌ 部分测试失败，请检查上面的错误信息")
        return 1

if __name__ == "__main__":
    import sys
    
    print("""
使用方法:
    python debug_asr.py                    # 基础测试
    python debug_asr.py /path/to/audio.mp3 # 测试真实音频
    """)
    
    exit_code = asyncio.run(main())
    sys.exit(exit_code)

