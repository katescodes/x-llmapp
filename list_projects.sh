#!/bin/bash
# 列出所有项目
# 通过直接查询数据库

echo "=========================================="
echo "查询所有招标项目"
echo "=========================================="
echo ""

# 方法1: 通过Docker直接查询PostgreSQL
echo "正在查询项目列表..."
echo ""

docker-compose exec -T postgres psql -U localgpt -d localgpt -t -c "
SELECT 
  id, 
  name, 
  TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') as created_at
FROM tender_projects 
ORDER BY created_at DESC 
LIMIT 20;
" 2>/dev/null | while IFS='|' read -r id name created_at; do
  # 去除空格
  id=$(echo "$id" | xargs)
  name=$(echo "$name" | xargs)
  created_at=$(echo "$created_at" | xargs)
  
  if [ -n "$id" ]; then
    echo "[$created_at] $name"
    echo "  项目ID: $id"
    echo ""
  fi
done

