#!/bin/bash
# ASR配置快速修复脚本

echo "🔧 ASR配置快速修复工具"
echo "================================"

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 检查是否在项目根目录
if [ ! -f "backend/.env" ] && [ ! -f "backend/env.example" ]; then
    echo -e "${RED}❌ 错误: 请在项目根目录运行此脚本${NC}"
    exit 1
fi

echo ""
echo "1️⃣  检查环境变量..."

# 检查.env文件
if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}⚠️  .env文件不存在，从example复制...${NC}"
    cp backend/env.example backend/.env
fi

# 检查ASR_ENABLED
if grep -q "^ASR_ENABLED=true" backend/.env; then
    echo -e "${GREEN}✅ ASR_ENABLED 已启用${NC}"
else
    if grep -q "^ASR_ENABLED=" backend/.env; then
        echo -e "${YELLOW}⚠️  修改 ASR_ENABLED 为 true...${NC}"
        sed -i 's/^ASR_ENABLED=.*/ASR_ENABLED=true/' backend/.env
    else
        echo -e "${YELLOW}⚠️  添加 ASR_ENABLED=true...${NC}"
        echo "" >> backend/.env
        echo "# ASR语音转文本服务" >> backend/.env
        echo "ASR_ENABLED=true" >> backend/.env
    fi
    echo -e "${GREEN}✅ ASR_ENABLED 已设置为 true${NC}"
fi

echo ""
echo "2️⃣  检查数据库迁移..."

# 检查Python环境
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ 未找到python3${NC}"
    exit 1
fi

# 运行迁移（如果迁移脚本存在）
if [ -f "backend/scripts/run_migrations.py" ]; then
    echo "运行数据库迁移..."
    cd backend
    python3 scripts/run_migrations.py
    cd ..
    echo -e "${GREEN}✅ 迁移完成${NC}"
else
    echo -e "${YELLOW}⚠️  未找到迁移脚本，跳过${NC}"
fi

echo ""
echo "3️⃣  验证数据库配置..."

# 检查数据库中的ASR配置
python3 - << 'PYTHON_SCRIPT'
import sys
import os
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

try:
    from app.services.db.postgres import get_conn
    
    with get_conn() as conn:
        with conn.cursor() as cur:
            # 检查表是否存在
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'asr_configs'
                )
            """)
            table_exists = cur.fetchone()[0]
            
            if not table_exists:
                print("❌ asr_configs 表不存在")
                print("   请运行: python backend/scripts/run_migrations.py")
                sys.exit(1)
            
            # 检查配置
            cur.execute("""
                SELECT COUNT(*) FROM asr_configs WHERE is_active = TRUE
            """)
            count = cur.fetchone()[0]
            
            if count == 0:
                print("⚠️  没有激活的ASR配置，添加默认配置...")
                
                # 添加默认配置
                cur.execute("""
                    INSERT INTO asr_configs (
                        id, name, api_url, model_name, response_format, 
                        is_active, is_default
                    ) VALUES (
                        'asr-default-001',
                        '默认语音转文本API',
                        'https://ai.yglinker.com:6399/v1/audio/transcriptions',
                        'whisper',
                        'verbose_json',
                        TRUE,
                        TRUE
                    )
                    ON CONFLICT (id) DO UPDATE 
                    SET is_active = TRUE, is_default = TRUE
                """)
                conn.commit()
                print("✅ 默认ASR配置已添加")
            else:
                print(f"✅ 找到 {count} 个激活的ASR配置")
                
                # 显示配置
                cur.execute("""
                    SELECT name, api_url, is_default 
                    FROM asr_configs 
                    WHERE is_active = TRUE
                    ORDER BY is_default DESC
                """)
                for row in cur.fetchall():
                    default_mark = " [默认]" if row[2] else ""
                    print(f"   - {row[0]}{default_mark}")
                    print(f"     {row[1]}")
    
    print("")
    print("✅ 数据库配置正常")
    sys.exit(0)
    
except Exception as e:
    print(f"❌ 数据库检查失败: {e}")
    sys.exit(1)
PYTHON_SCRIPT

DB_CHECK_RESULT=$?

if [ $DB_CHECK_RESULT -ne 0 ]; then
    echo -e "${RED}❌ 数据库配置有问题${NC}"
    echo ""
    echo "请执行以下操作:"
    echo "1. 确保数据库正常运行"
    echo "2. 运行迁移: python backend/scripts/run_migrations.py"
    echo "3. 重新运行此脚本"
    exit 1
fi

echo ""
echo "4️⃣  运行ASR诊断测试..."

if [ -f "debug_asr.py" ]; then
    python3 debug_asr.py
    TEST_RESULT=$?
    
    if [ $TEST_RESULT -eq 0 ]; then
        echo ""
        echo -e "${GREEN}================================${NC}"
        echo -e "${GREEN}🎉 ASR配置修复完成！${NC}"
        echo -e "${GREEN}================================${NC}"
        echo ""
        echo "接下来："
        echo "1. 重启后端服务（如果正在运行）"
        echo "2. 在系统中上传音频文件测试转写功能"
        echo ""
    else
        echo ""
        echo -e "${YELLOW}================================${NC}"
        echo -e "${YELLOW}⚠️  配置完成但测试失败${NC}"
        echo -e "${YELLOW}================================${NC}"
        echo ""
        echo "可能的原因："
        echo "1. ASR API服务不可访问"
        echo "2. 网络连接问题"
        echo "3. API密钥错误（如果需要）"
        echo ""
        echo "请查看上面的错误信息并："
        echo "- 检查API地址是否正确"
        echo "- 测试网络连接"
        echo "- 查看详细文档: docs/ASR_TROUBLESHOOTING.md"
    fi
else
    echo -e "${YELLOW}⚠️  未找到 debug_asr.py，跳过测试${NC}"
    echo -e "${GREEN}✅ 配置修复完成${NC}"
fi

echo ""
echo "详细文档: docs/ASR_TROUBLESHOOTING.md"

