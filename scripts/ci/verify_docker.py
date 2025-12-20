#!/usr/bin/env python3
"""
Docker环境验证脚本
启动docker compose并运行完整验收
"""
import os
import subprocess
import sys
import time
from pathlib import Path


def run_cmd(cmd: list, capture=False):
    """运行命令"""
    print(f"$ {' '.join(cmd)}")
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    else:
        return subprocess.run(cmd).returncode


def main():
    repo_root = Path(__file__).parent.parent.parent
    os.chdir(repo_root)
    
    reports_dir = repo_root / "reports" / "verify"
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 70)
    print("  Docker 环境验证")
    print("=" * 70)
    print()
    
    # Step 1: 启动docker compose
    print("Step 1: 启动 Docker Compose 服务...")
    ret = run_cmd(["docker-compose", "up", "-d"])
    if ret != 0:
        print("✗ Docker Compose 启动失败")
        return 1
    print("✓ Docker Compose 服务已启动")
    print()
    
    # Step 2: 等待backend健康
    print("Step 2: 等待 Backend 就绪...")
    backend_url = "http://192.168.2.17:9001/api/_debug/health"
    max_wait = 60
    for i in range(max_wait):
        try:
            import requests
            resp = requests.get(backend_url, timeout=2)
            if resp.status_code == 200:
                print(f"✓ Backend 就绪 (耗时 {i+1}s)")
                break
        except:
            pass
        time.sleep(1)
    else:
        print(f"✗ Backend 在 {max_wait}s 内未就绪")
        # 导出日志
        print("导出 docker logs...")
        for service in ["backend", "worker", "redis", "postgres"]:
            log_file = reports_dir / f"docker_{service}.log"
            ret, stdout, stderr = run_cmd(
                ["docker-compose", "logs", service, "--tail", "300"],
                capture=True
            )
            with open(log_file, 'w') as f:
                f.write(stdout)
                if stderr:
                    f.write("\n=== STDERR ===\n")
                    f.write(stderr)
            print(f"  {log_file}")
        return 1
    print()
    
    # Step 3: 运行验收脚本
    print("Step 3: 运行完整验收...")
    ret = run_cmd([
        "python",
        "scripts/ci/verify_cutover_and_extraction.py"
    ])
    
    if ret != 0:
        print()
        print("✗ 验收失败，导出 docker logs...")
        for service in ["backend", "worker", "redis", "postgres"]:
            log_file = reports_dir / f"docker_{service}.log"
            ret_code, stdout, stderr = run_cmd(
                ["docker-compose", "logs", service, "--tail", "300"],
                capture=True
            )
            with open(log_file, 'w') as f:
                f.write(stdout)
                if stderr:
                    f.write("\n=== STDERR ===\n")
                    f.write(stderr)
            print(f"  {log_file}")
        return 1
    
    print()
    print("=" * 70)
    print("  ✓ Docker 验证通过！")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())

