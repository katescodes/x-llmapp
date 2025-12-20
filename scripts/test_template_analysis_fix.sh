#!/bin/bash
# 测试模板分析功能是否正常

echo "======================================"
echo "测试模板分析功能"
echo "======================================"
echo ""

# 检查后端是否启动
echo "1. 检查后端服务..."
if curl -s http://localhost:9001/docs > /dev/null; then
    echo "   ✅ 后端服务正常"
else
    echo "   ❌ 后端服务不可用"
    exit 1
fi

# 检查API路由是否注册
echo ""
echo "2. 检查API路由..."
ROUTES=$(curl -s http://localhost:9001/openapi.json | grep -o "/api/apps/tender/templates/.*analysis" | head -3)
if [ -n "$ROUTES" ]; then
    echo "   ✅ API路由已注册："
    echo "$ROUTES" | sed 's/^/      /'
else
    echo "   ❌ API路由未找到"
    exit 1
fi

# 检查前端是否启动
echo ""
echo "3. 检查前端服务..."
if curl -s http://localhost:6173 > /dev/null; then
    echo "   ✅ 前端服务正常"
else
    echo "   ❌ 前端服务不可用"
    exit 1
fi

# 检查数据库迁移
echo ""
echo "4. 检查数据库..."
docker-compose exec -T backend python -c "
import psycopg
from psycopg_pool import ConnectionPool

pool = ConnectionPool('postgresql://localgpt:localgpt@postgres:5432/localgpt', min_size=1, max_size=1)
with pool.connection() as conn:
    with conn.cursor() as cur:
        cur.execute(\"\"\"
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'format_templates' 
            AND column_name = 'analysis_json'
        \"\"\")
        result = cur.fetchone()
        if result:
            print('   ✅ analysis_json 字段存在')
        else:
            print('   ❌ analysis_json 字段不存在')
            exit(1)
" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "   数据库检查通过"
else
    echo "   ❌ 数据库检查失败"
    exit 1
fi

echo ""
echo "======================================"
echo "✅ 所有检查通过！"
echo "======================================"
echo ""
echo "📱 现在可以使用前端测试："
echo "   1. 访问: http://localhost:6173"
echo "   2. 进入"格式模板管理""
echo "   3. 点击"查看详情""
echo "   4. 切换到"🤖 模板分析"Tab"
echo "   5. 点击"🔄 重新解析"按钮"
echo ""
echo "🔍 查看后端日志："
echo "   docker-compose logs -f backend | grep -i analysis"
echo ""

