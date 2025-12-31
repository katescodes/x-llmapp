"""
测试目录规则细化功能

测试逻辑：
1. 选择一个已有招标要求数据的项目
2. 生成目录
3. 检查是否进行了规则细化
4. 验证细化节点的正确性
"""
import requests
import json
import time
from typing import Dict, Any

API_BASE = "http://192.168.2.17/api"
USERNAME = "admin"
PASSWORD = "admin123"

def login() -> str:
    """登录获取token"""
    resp = requests.post(f"{API_BASE}/v1/auth/login", json={
        "username": USERNAME,
        "password": PASSWORD
    })
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"]

def get_projects(token: str):
    """获取项目列表"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{API_BASE}/apps/tender/projects", headers=headers)
    resp.raise_for_status()
    return resp.json()

def get_project_requirements(token: str, project_id: str):
    """获取项目招标要求"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{API_BASE}/apps/tender/projects/{project_id}/requirements", headers=headers)
    resp.raise_for_status()
    return resp.json()

def generate_directory(token: str, project_id: str) -> Dict[str, Any]:
    """生成目录"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.post(
        f"{API_BASE}/apps/tender/projects/{project_id}/generate-directory",
        headers=headers,
        json={}
    )
    resp.raise_for_status()
    return resp.json()

def get_run_status(token: str, run_id: str) -> Dict[str, Any]:
    """获取运行状态"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{API_BASE}/apps/tender/runs/{run_id}", headers=headers)
    resp.raise_for_status()
    return resp.json()

def get_directory(token: str, project_id: str):
    """获取目录"""
    headers = {"Authorization": f"Bearer {token}"}
    resp = requests.get(f"{API_BASE}/apps/tender/projects/{project_id}/directory", headers=headers)
    resp.raise_for_status()
    return resp.json()

def main():
    print("=" * 80)
    print("目录规则细化功能测试")
    print("=" * 80)
    
    # 1. 登录
    print("\n[1/6] 登录...")
    token = login()
    print("✅ 登录成功")
    
    # 2. 获取项目列表
    print("\n[2/6] 获取项目列表...")
    projects = get_projects(token)
    if not projects:
        print("❌ 没有项目，测试终止")
        return
    
    print(f"✅ 找到 {len(projects)} 个项目")
    for i, proj in enumerate(projects[:5]):
        print(f"  {i+1}. {proj['name']} (ID: {proj['id']})")
    
    # 3. 选择项目（优先选择"测试2"）
    print("\n[3/6] 选择测试项目...")
    test_project = None
    for proj in projects:
        if "测试2" in proj['name']:
            test_project = proj
            break
    
    if not test_project:
        test_project = projects[0]
    
    project_id = test_project['id']
    print(f"✅ 选择项目: {test_project['name']} (ID: {project_id})")
    
    # 4. 检查是否有招标要求
    print("\n[4/6] 检查招标要求...")
    try:
        requirements = get_project_requirements(token, project_id)
        req_count = len(requirements) if isinstance(requirements, list) else 0
        print(f"✅ 该项目有 {req_count} 条招标要求")
        
        if req_count == 0:
            print("⚠️  没有招标要求，细化功能不会生效，但仍然测试基础功能")
        else:
            # 统计各维度的要求数量
            dimension_count = {}
            for req in requirements:
                dim = req.get('dimension', 'other')
                dimension_count[dim] = dimension_count.get(dim, 0) + 1
            
            print("\n招标要求维度分布：")
            for dim, count in sorted(dimension_count.items(), key=lambda x: -x[1]):
                print(f"  - {dim}: {count}条")
    except Exception as e:
        print(f"⚠️  无法获取招标要求: {e}")
        req_count = 0
    
    # 5. 生成目录
    print("\n[5/6] 生成目录...")
    try:
        gen_resp = generate_directory(token, project_id)
        run_id = gen_resp.get('run_id')
        print(f"✅ 目录生成任务已启动 (run_id: {run_id})")
        
        # 等待完成
        print("\n等待目录生成完成...")
        max_wait = 120  # 最多等待2分钟
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            run_status = get_run_status(token, run_id)
            status = run_status.get('status')
            progress = run_status.get('progress', 0)
            
            print(f"  状态: {status}, 进度: {progress:.0%}", end='\r')
            
            if status == 'success':
                print("\n✅ 目录生成成功")
                
                # 提取生成模式和统计信息
                result_json = run_status.get('result_json', {})
                generation_mode = result_json.get('generation_mode', 'unknown')
                fast_stats = result_json.get('fast_stats', {})
                refinement_stats = result_json.get('refinement_stats', {})
                
                print(f"\n生成模式: {generation_mode}")
                print(f"快速统计: {json.dumps(fast_stats, ensure_ascii=False)}")
                print(f"细化统计: {json.dumps(refinement_stats, ensure_ascii=False)}")
                
                break
            elif status == 'failed':
                print(f"\n❌ 目录生成失败: {run_status.get('message')}")
                return
            
            time.sleep(2)
        else:
            print(f"\n⏱️  超时（{max_wait}秒），停止等待")
            return
            
    except Exception as e:
        print(f"❌ 目录生成失败: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 6. 获取目录并分析
    print("\n[6/6] 分析生成的目录...")
    try:
        directory = get_directory(token, project_id)
        nodes = directory if isinstance(directory, list) else directory.get('nodes', [])
        
        print(f"\n✅ 获取到 {len(nodes)} 个目录节点")
        
        # 统计层级分布
        level_count = {}
        source_count = {}
        refinement_nodes = []
        
        for node in nodes:
            level = node.get('level', 0)
            source = node.get('source', 'unknown')
            level_count[level] = level_count.get(level, 0) + 1
            source_count[source] = source_count.get(source, 0) + 1
            
            if source == 'refinement_rule':
                refinement_nodes.append(node)
        
        print("\n目录层级分布：")
        for level in sorted(level_count.keys()):
            print(f"  Level {level}: {level_count[level]}个节点")
        
        print("\n节点来源分布：")
        for source in sorted(source_count.keys()):
            print(f"  {source}: {source_count[source]}个节点")
        
        # 重点检查细化节点
        if refinement_nodes:
            print(f"\n✨ 细化节点详情（共{len(refinement_nodes)}个）：")
            for i, node in enumerate(refinement_nodes[:10], 1):  # 只显示前10个
                print(f"  {i}. [{node.get('level')}级] {node.get('title')}")
                print(f"     父节点: {node.get('parent_ref')}")
                if node.get('meta'):
                    meta = node['meta']
                    print(f"     维度: {meta.get('dimension')}, 类型: {meta.get('req_type')}")
                    if meta.get('score'):
                        print(f"     分值: {meta.get('score')}分")
            
            if len(refinement_nodes) > 10:
                print(f"  ... 还有 {len(refinement_nodes) - 10} 个细化节点")
        else:
            if req_count > 0:
                print("\n⚠️  未发现细化节点（可能招标要求的维度与目录节点不匹配）")
            else:
                print("\n⚠️  未发现细化节点（因为该项目没有招标要求）")
        
        # 验证细化统计的准确性
        if refinement_stats and refinement_stats.get('enabled'):
            expected_new_nodes = refinement_stats.get('new_nodes', 0)
            actual_refinement_nodes = len(refinement_nodes)
            
            print(f"\n📊 细化统计验证：")
            print(f"  预期新增节点: {expected_new_nodes}")
            print(f"  实际细化节点: {actual_refinement_nodes}")
            
            if expected_new_nodes == actual_refinement_nodes:
                print("  ✅ 统计一致")
            else:
                print(f"  ⚠️  统计不一致（差异: {abs(expected_new_nodes - actual_refinement_nodes)}）")
        
        print("\n" + "=" * 80)
        print("✅ 测试完成")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ 获取目录失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

