"""
招投标端到端 Smoke 测试

使用 pytest 运行：
    pytest -m smoke
    pytest tests/smoke/test_tender_e2e.py -v
"""
import os
import subprocess
import sys
import pytest
from pathlib import Path


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


@pytest.mark.smoke
def test_tender_e2e_smoke():
    """
    招投标端到端冒烟测试
    
    通过调用 scripts/smoke/tender_e2e.py 脚本来执行完整的端到端测试流程。
    """
    script_path = PROJECT_ROOT / "scripts" / "smoke" / "tender_e2e.py"
    
    # 确保脚本存在
    assert script_path.exists(), f"Smoke 脚本不存在: {script_path}"
    
    # 设置环境变量
    env = os.environ.copy()
    env.setdefault("BASE_URL", "http://localhost:9001")
    env.setdefault("USERNAME", "admin@example.com")
    env.setdefault("PASSWORD", "admin123")
    env.setdefault("SKIP_OPTIONAL", "false")
    env.setdefault("KEEP_PROJECT", "false")  # 测试后清理
    
    # 执行脚本
    result = subprocess.run(
        [sys.executable, str(script_path)],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT)
    )
    
    # 打印输出（用于调试）
    if result.stdout:
        print("\n" + "=" * 60)
        print("STDOUT:")
        print("=" * 60)
        print(result.stdout)
    
    if result.stderr:
        print("\n" + "=" * 60)
        print("STDERR:")
        print("=" * 60)
        print(result.stderr)
    
    # 检查返回码
    assert result.returncode == 0, f"Smoke 测试失败，退出码: {result.returncode}"


@pytest.mark.smoke
@pytest.mark.parametrize("skip_optional", [True, False])
def test_tender_e2e_with_options(skip_optional):
    """
    测试不同配置选项下的端到端流程
    
    Args:
        skip_optional: 是否跳过可选步骤
    """
    script_path = PROJECT_ROOT / "scripts" / "smoke" / "tender_e2e.py"
    assert script_path.exists(), f"Smoke 脚本不存在: {script_path}"
    
    # 设置环境变量
    env = os.environ.copy()
    env.setdefault("BASE_URL", "http://localhost:9001")
    env.setdefault("USERNAME", "admin@example.com")
    env.setdefault("PASSWORD", "admin123")
    env["SKIP_OPTIONAL"] = "true" if skip_optional else "false"
    env["KEEP_PROJECT"] = "false"
    
    # 执行脚本
    result = subprocess.run(
        [sys.executable, str(script_path)],
        env=env,
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT)
    )
    
    # 检查返回码
    assert result.returncode == 0, f"Smoke 测试失败 (skip_optional={skip_optional})，退出码: {result.returncode}"


if __name__ == "__main__":
    # 允许直接运行此文件
    pytest.main([__file__, "-v"])









