#!/bin/bash
# 版本发布脚本

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== x-llmapp 版本发布工具 ===${NC}\n"

# 检查是否有未提交的更改
if [[ -n $(git status -s) ]]; then
    echo -e "${RED}错误: 有未提交的更改，请先提交或暂存${NC}"
    git status -s
    exit 1
fi

# 获取当前版本
CURRENT_VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "v0.0.0")
echo -e "当前版本: ${YELLOW}${CURRENT_VERSION}${NC}"

# 解析版本号
VERSION_NUM=${CURRENT_VERSION#v}
IFS='.' read -r -a VERSION_PARTS <<< "$VERSION_NUM"
MAJOR=${VERSION_PARTS[0]}
MINOR=${VERSION_PARTS[1]}
PATCH=${VERSION_PARTS[2]}

# 选择版本类型
echo -e "\n请选择版本类型:"
echo "1) Patch (补丁: v${MAJOR}.${MINOR}.$((PATCH+1)))"
echo "2) Minor (次版本: v${MAJOR}.$((MINOR+1)).0)"
echo "3) Major (主版本: v$((MAJOR+1)).0.0)"
echo "4) 自定义版本"
read -p "请选择 (1-4): " CHOICE

case $CHOICE in
    1)
        NEW_VERSION="v${MAJOR}.${MINOR}.$((PATCH+1))"
        ;;
    2)
        NEW_VERSION="v${MAJOR}.$((MINOR+1)).0"
        ;;
    3)
        NEW_VERSION="v$((MAJOR+1)).0.0"
        ;;
    4)
        read -p "请输入版本号 (例如: v0.3.0): " NEW_VERSION
        ;;
    *)
        echo -e "${RED}无效选择${NC}"
        exit 1
        ;;
esac

echo -e "\n新版本: ${GREEN}${NEW_VERSION}${NC}"

# 输入版本说明
echo -e "\n请输入版本说明 (按 Ctrl+D 结束):"
RELEASE_NOTES=$(cat)

# 确认
read -p "确认创建版本 ${NEW_VERSION}? (y/n): " CONFIRM
if [[ "$CONFIRM" != "y" ]]; then
    echo "取消发布"
    exit 0
fi

# 创建标签
echo -e "\n${YELLOW}创建 Git 标签...${NC}"
git tag -a "$NEW_VERSION" -m "Release $NEW_VERSION

$RELEASE_NOTES"

# 推送
echo -e "${YELLOW}推送到 GitHub...${NC}"
git push origin main
git push origin "$NEW_VERSION"

echo -e "\n${GREEN}✅ 版本 ${NEW_VERSION} 发布成功！${NC}"
echo -e "查看发布: https://github.com/katescodes/x-llmapp/releases/tag/${NEW_VERSION}"

