#!/usr/bin/env python3
"""Create an offline deployment bundle for x-llm."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tarfile
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_IMAGES = (
    ("x-llm-backend:local", "x-llm-backend_local.tar"),
    ("x-llm-frontend:local", "x-llm-frontend_local.tar"),
    ("postgres:15-alpine", "postgres_15-alpine.tar"),
)

COPY_IGNORE_PATTERNS = (
    ".git",
    ".idea",
    ".vscode",
    ".pytest_cache",
    "__pycache__",
    "node_modules",
    "dist",
    ".cursor",
    "terminals",
    "*.pyc",
    "*.pyo",
    "*.log",
    "*.tmp",
)


def run(cmd: Iterable[str], *, cwd: Path | None = None) -> None:
    display = " ".join(cmd)
    print(f"[offline-bundle] $ {display}")
    subprocess.run(cmd, cwd=cwd, check=True)


def ensure_images(skip_build: bool) -> None:
    if not skip_build:
        run(["docker", "compose", "build", "backend", "frontend"], cwd=PROJECT_ROOT)
    run(["docker", "pull", "postgres:15-alpine"])


def save_images(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for image, filename in DEFAULT_IMAGES:
        target = output_dir / filename
        run(["docker", "save", "-o", str(target), image])


def copy_project_tree(destination: Path) -> None:
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(
        PROJECT_ROOT,
        destination,
        ignore=shutil.ignore_patterns(*COPY_IGNORE_PATTERNS),
    )


def write_helper_scripts(bundle_dir: Path) -> None:
    sh_script = bundle_dir / "offline-load.sh"
    sh_script.write_text(
        """#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)"
IMAGE_DIR="$SCRIPT_DIR/docker-images"
PROJECT_DIR="$SCRIPT_DIR/source"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker 命令不存在，请先安装 Docker 与 Docker Compose v2" >&2
  exit 1
fi

echo ">>> 加载离线镜像..."
for image_tar in "$IMAGE_DIR"/*.tar; do
  [ -f "$image_tar" ] || continue
  docker load -i "$image_tar"
done

echo ">>> 启动 x-llm 容器..."
cd "$PROJECT_DIR"
docker compose up -d

echo "完成，默认前端端口为 http://<当前主机>:6173"
"""
    )
    sh_script.chmod(0o755)

    ps_script = bundle_dir / "offline-load.ps1"
    ps_script.write_text(
        """#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ImageDir = Join-Path $ScriptDir "docker-images"
$ProjectDir = Join-Path $ScriptDir "source"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "未检测到 docker，请先安装 Docker + Docker Compose v2"
}

Write-Host ">>> 加载离线镜像..."
Get-ChildItem -Path $ImageDir -Filter *.tar | ForEach-Object {
    docker load --input $_.FullName
}

Write-Host ">>> 启动 x-llm 容器..."
Set-Location $ProjectDir
docker compose up -d

Write-Host "完成，默认前端端口 http://<当前主机>:6173"
"""
    )


def write_readme(bundle_dir: Path) -> None:
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%SZ")
    readme = bundle_dir / "README_OFFLINE.md"
    readme.write_text(
        textwrap.dedent(
            f"""
            # x-llm 离线部署包

            生成时间：{timestamp}

            ## 目录结构

            - `source/`：完整的项目源码与数据（含 `data/`）
            - `docker-images/`：预打包的 Docker 镜像 (`x-llm-backend`, `x-llm-frontend`, `postgres:15-alpine`)
            - `offline-load.sh` / `offline-load.ps1`：离线环境一键导入 & 启动脚本

            ## 目标环境前置条件

            - 已安装 Docker 与 Docker Compose v2
            - 已复制 `.env`、密钥文件等必要配置（如果不在源码内，请自行放入 `source/`）
            - (可选) 更新 `source/docker-compose.yml` 内的端口映射或环境变量

            ## 使用方法

            1. 将本压缩包复制至目标离线服务器并解压：
               ```bash
               tar -xzf x-llm-offline-bundle.tar.gz
               ```
            2. 进入解压目录，运行对应脚本：
               - Linux/macOS：`./offline-load.sh`
               - Windows (PowerShell 7+)：`pwsh ./offline-load.ps1`
            3. 启动完成后，默认前端监听 `http://<主机>:6173`，后端 API `http://<主机>:9001`
            4. 如需以 HTTPS/域名方式暴露，请在离线服务器自行配置 Nginx 等反向代理

            ## 升级与重复运行

            - 每次在有网络的机器重新执行 `scripts/offline_bundle.py` 即可生成新的离线包
            - 目标机更新时，先停止原容器 `cd source && docker compose down`，再运行最新的导入脚本
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def create_bundle(archive_path: Path, skip_build: bool) -> None:
    ensure_images(skip_build)

    with tempfile.TemporaryDirectory(prefix="x-llm-offline-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        bundle_name = f"x-llm-offline-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        bundle_dir = tmp_dir / bundle_name
        bundle_dir.mkdir(parents=True, exist_ok=True)

        images_dir = bundle_dir / "docker-images"
        save_images(images_dir)

        source_dir = bundle_dir / "source"
        copy_project_tree(source_dir)

        write_helper_scripts(bundle_dir)
        write_readme(bundle_dir)

        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(bundle_dir, arcname=bundle_name)

    print(f"[offline-bundle] Bundle ready -> {archive_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="x-llm 离线部署包打包工具")
    parser.add_argument(
        "-o",
        "--output",
        default=str(PROJECT_ROOT / "dist" / "x-llm-offline-bundle.tar.gz"),
        help="输出离线包路径（默认 dist/x-llm-offline-bundle.tar.gz）",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="跳过 docker compose build（已手动构建时可使用）",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="如目标文件已存在则覆盖",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive_path = Path(args.output).resolve()
    if archive_path.exists() and not args.force:
        raise SystemExit(
            f"目标文件 {archive_path} 已存在，请使用 --force 覆盖或指定新路径"
        )
    create_bundle(archive_path, args.skip_build)


if __name__ == "__main__":
    main()

