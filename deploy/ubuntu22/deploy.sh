#!/usr/bin/env bash
set -euo pipefail
ECG_DEPLOY_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ECG_DEPLOY_ROOT"

if ! command -v docker >/dev/null 2>&1; then
  echo "请先运行：sudo bash deploy/ubuntu22/install-docker.sh" >&2
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "缺少 Docker Compose plugin，请运行安装脚本。" >&2
  exit 1
fi
if [[ ! -f deploy/ubuntu22/.env ]]; then
  cp deploy/ubuntu22/.env.example deploy/ubuntu22/.env
fi
docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml config --quiet
docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml up -d --build --wait --wait-timeout 240
docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml exec -T ecg-ai python deploy/ubuntu22/verify_bundle.py --api http://127.0.0.1:8000
echo "部署完成。默认访问 http://服务器IP:8000/；端口以 deploy/ubuntu22/.env 为准。"
echo "日志：sudo docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml logs -f --tail=100"
