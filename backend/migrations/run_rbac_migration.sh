#!/bin/bash
# 运行权限管理迁移脚本

# 设置数据库连接信息（从环境变量或默认值）
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-x_llmapp}"
DB_USER="${DB_USER:-postgres}"

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "📦 开始执行权限管理数据库迁移..."
echo "数据库: $DB_NAME @ $DB_HOST:$DB_PORT"
echo ""

# 执行迁移
PGPASSWORD="${DB_PASSWORD}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -f "$SCRIPT_DIR/030_create_rbac_tables.sql"

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 权限管理数据库迁移完成！"
else
    echo ""
    echo "❌ 迁移失败，请检查错误信息"
    exit 1
fi

