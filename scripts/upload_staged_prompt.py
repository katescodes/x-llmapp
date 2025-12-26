#!/usr/bin/env python3
"""
Upload staged prompt template to database
"""
import requests
import sys
from pathlib import Path

# 配置
BASE_URL = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin123"

def login():
    """登录获取token"""
    resp = requests.post(
        f"{BASE_URL}/api/platform/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    resp.raise_for_status()
    token = resp.json()["token"]
    print(f"✅ 登录成功")
    return token

def upload_prompt(token: str):
    """上传Prompt模板到数据库"""
    # 读取Prompt文件
    prompt_file = Path(__file__).parent.parent / "backend" / "app" / "works" / "tender" / "prompts" / "project_info_v2_staged.md"
    
    if not prompt_file.exists():
        print(f"❌ Prompt文件不存在: {prompt_file}")
        sys.exit(1)
    
    with open(prompt_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"📄 读取Prompt文件: {prompt_file}")
    print(f"📏 文件大小: {len(content)} 字符")
    
    # 创建Prompt模板
    resp = requests.post(
        f"{BASE_URL}/api/apps/tender/prompts/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "module": "project_info_staged",
            "name": "项目信息提取（四阶段）",
            "description": "分四个阶段顺序抽取：1.项目基本信息 2.技术参数 3.商务条款 4.评分规则",
            "content": content
        }
    )
    
    if resp.status_code == 201 or resp.status_code == 200:
        result = resp.json()
        prompt_id = result.get("prompt_id")
        print(f"✅ Prompt模板已上传到数据库")
        print(f"   ID: {prompt_id}")
        print(f"   模块: project_info_staged")
        print(f"   名称: 项目信息提取（四阶段）")
        return prompt_id
    else:
        print(f"❌ 上传失败: {resp.status_code}")
        print(f"   响应: {resp.text}")
        sys.exit(1)

def main():
    print("=" * 60)
    print("上传四阶段Prompt模板到数据库")
    print("=" * 60)
    
    try:
        # 1. 登录
        token = login()
        
        # 2. 上传Prompt
        prompt_id = upload_prompt(token)
        
        print("\n" + "=" * 60)
        print("✅ 完成！")
        print("=" * 60)
        print(f"\nPrompt ID: {prompt_id}")
        print("\n后续操作：")
        print("1. 访问系统设置 -> Prompt管理 查看模板")
        print("2. 确认模板已激活（is_active = true）")
        print("3. 执行项目信息抽取测试")
        
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

