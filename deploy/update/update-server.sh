#!/usr/bin/env bash
set -euo pipefail
if [[ $# -ne 1 ]]; then
  echo "用法：sudo bash update-server.sh /已有项目的绝对路径" >&2
  exit 1
fi
ECG_UPDATE_PACKAGE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ECG_UPDATE_TARGET="$(cd -- "$1" && pwd)"
python3 "$ECG_UPDATE_PACKAGE/apply_update.py" "$ECG_UPDATE_TARGET" --package "$ECG_UPDATE_PACKAGE"
cd "$ECG_UPDATE_TARGET"
bash deploy/ubuntu22/deploy.sh
echo "更新完成。访问原来的服务器网址即可。"
