#!/usr/bin/env python3
"""
录音下载功能调试脚本
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from app.services.db.postgres import get_conn
from pathlib import Path

print("🔍 检查录音文件状态\n")
print("="*60)

try:
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 查询所有录音
            cur.execute("""
                SELECT id, user_id, title, filename, audio_path, 
                       keep_audio, file_size, audio_format, created_at
                FROM voice_recordings
                WHERE deleted_at IS NULL
                ORDER BY created_at DESC
                LIMIT 10
            """)
            
            recordings = cur.fetchall()
            
            if not recordings:
                print("❌ 数据库中没有录音记录")
                sys.exit(1)
            
            print(f"找到 {len(recordings)} 条录音记录:\n")
            
            for rec in recordings:
                print(f"📼 录音 ID: {rec['id']}")
                print(f"   标题: {rec['title']}")
                print(f"   文件名: {rec['filename']}")
                print(f"   格式: {rec['audio_format']}")
                print(f"   保留音频: {'✅' if rec['keep_audio'] else '❌'}")
                print(f"   文件大小: {rec['file_size']} bytes")
                print(f"   音频路径: {rec['audio_path']}")
                
                # 检查文件是否存在
                if rec['audio_path']:
                    audio_file = Path(rec['audio_path'])
                    if audio_file.exists():
                        actual_size = audio_file.stat().st_size
                        print(f"   文件状态: ✅ 存在 (实际大小: {actual_size} bytes)")
                        
                        # 检查权限
                        if audio_file.is_file():
                            if os.access(audio_file, os.R_OK):
                                print(f"   文件权限: ✅ 可读")
                            else:
                                print(f"   文件权限: ❌ 不可读")
                        else:
                            print(f"   文件类型: ❌ 不是普通文件")
                    else:
                        print(f"   文件状态: ❌ 不存在")
                else:
                    print(f"   音频路径: ❌ 未设置")
                
                print()
            
            # 统计
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN keep_audio = TRUE THEN 1 END) as with_audio,
                    COUNT(CASE WHEN audio_path IS NOT NULL THEN 1 END) as with_path
                FROM voice_recordings
                WHERE deleted_at IS NULL
            """)
            stats = cur.fetchone()
            
            print("="*60)
            print("📊 统计信息:")
            print(f"   总录音数: {stats['total']}")
            print(f"   保留音频: {stats['with_audio']}")
            print(f"   有音频路径: {stats['with_path']}")
            
except Exception as e:
    print(f"❌ 检查失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("💡 提示:")
print("1. 如果文件不存在，说明音频文件丢失或路径错误")
print("2. 如果文件不可读，需要检查文件权限")
print("3. 如果 keep_audio=False，说明录音时没有选择保留音频")
print("4. 重启后端服务后再次尝试下载")

