# ECG-AI V6 完整包上传与启动

发布日：2026年11月19日。适用于 Ubuntu 22.04、amd64/x86_64、Docker CPU 部署。ZIP 是完整网页运行包，包含48条原始记录、6个原生产模型、60个研究检查点、预构建前端、结果、部署脚本以及 V6 论文 Word/PDF。服务器无需训练或安装 Node.js。第一次 Docker 构建需要联网下载基础镜像与固定依赖；ZIP 不含 Docker 镜像。

## 1 在本地 PowerShell 上传

先进入 ZIP 所在文件夹，再执行。以下服务器地址沿用现有项目文档。

```powershell
Get-FileHash .\ECG-AI_Full_Server_V6_20261119.zip -Algorithm SHA256
scp .\ECG-AI_Full_Server_V6_20261119.zip .\ECG-AI_Full_Server_V6_20261119.zip.sha256 root@47.83.150.55:/tmp/
ssh root@47.83.150.55
```

## 2 在服务器校验并解压到新目录

整个代码块复制执行；任何一步失败立即停止后续步骤。保留原 `/root/ecg-ai`，本次使用新目录，避免覆盖本地源码或配置。重复执行时新目录必须不存在，可另选一个目录名。

```bash
set -euo pipefail
cd /tmp
sha256sum -c ECG-AI_Full_Server_V6_20261119.zip.sha256
python3 - <<'PY'
from pathlib import Path, PurePosixPath
import zipfile
archive = Path('/tmp/ECG-AI_Full_Server_V6_20261119.zip')
target = Path('/root/ecg-ai-v6-20261119')
if target.exists():
    raise SystemExit('目标目录已存在：请另选新目录，不要覆盖现有项目。')
with zipfile.ZipFile(archive) as z:
    bad = z.testzip()
    if bad:
        raise SystemExit('ZIP损坏：' + bad)
    for name in z.namelist():
        p = PurePosixPath(name)
        if p.is_absolute() or '..' in p.parts or '\\' in name or not p.parts or p.parts[0] != 'ecg-ai':
            raise SystemExit('不安全或错误的归档路径：' + name)
    z.extractall(target)
print('解压完成：', target / 'ecg-ai')
PY
cd /root/ecg-ai-v6-20261119/ecg-ai
python3 - <<'PY'
import hashlib, json
from pathlib import Path
root = Path.cwd()
manifest = json.loads((root/'DELIVERY_MANIFEST.json').read_text(encoding='utf-8'))
for row in manifest['files']:
    p = root/row['path']
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest() != row['sha256']:
        raise SystemExit('文件校验失败：' + row['path'])
print('完整包校验通过：', len(manifest['files']), '个文件')
PY
```

服务器建议预留至少 8 GB 可用磁盘供镜像构建、包和日志使用；实际占用随镜像缓存变化。Python 3 用于 ZIP 解压与校验，应用的 Python 3.12 位于容器内。

## 3 保留配置并启动

如果原项目路径不是 `/root/ecg-ai`，修改下面复制配置的来源。新部署没有该文件时，会使用默认8000端口。运行安装脚本前需已具有sudo权限；以root登录时可以直接使用这些命令。

```bash
cd /root/ecg-ai-v6-20261119/ecg-ai
if [ -f /root/ecg-ai/deploy/ubuntu22/.env ]; then
  cp -n /root/ecg-ai/deploy/ubuntu22/.env deploy/ubuntu22/.env
fi
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  sudo bash deploy/ubuntu22/install-docker.sh
fi
sudo bash deploy/ubuntu22/deploy.sh
```

Compose项目名固定为 `ecg-ai`，因此从旧包更新时复用相同命名游戏数据卷。不要执行 `docker compose down -v` 或删除游戏卷。原代码目录和 `.env` 保留；新容器启动后由新目录管理服务。若旧服务器手动改过Compose项目名或游戏数据库挂载方式，应先核对其卷名与备份数据库，再启动本包。

## 4 验收与访问

部署脚本自动执行模型和API校验。默认端口的补充检查：

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/rhythm/summary \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("训练数:",len(d["folds"]),"种子:",d["config"]["seeds"],"可靠性汇总:",len(d["uncertainty"]["results"]))'
sudo docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml ps
```

预期：健康状态 `ok`、6个原模型就绪；训练数60，种子3个，可靠性汇总24组。自定义端口时把8000改为 `.env` 中的值。

浏览器访问：

- 首页：http://47.83.150.55:8000/
- 节律融合实验室：http://47.83.150.55:8000/rhythm-lab

已有页面按Ctrl+F5刷新。若服务器本机curl正常但外网打不开，在云服务器安全组允许实际使用的TCP端口；如启用了UFW，也放行该端口。

## 5 日志、重启与回退

```bash
cd /root/ecg-ai-v6-20261119/ecg-ai
sudo docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml logs --tail=100
sudo docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml restart
```

如需恢复旧应用，在保留的原项目目录重新运行其 `deploy/ubuntu22/deploy.sh`，由旧源码重建相同Compose项目；不要删除命名数据卷。只有实际存在且已确认正确的旧目录才用于回退。

## 6 同一个 ZIP 在本地运行

解压后进入 `ecg-ai` 文件夹。Windows安装64位Python 3.12后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1 -CheckOnly
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

首次联网安装固定CPU依赖，之后访问 http://127.0.0.1:8000/rhythm-lab 。安装Docker的机器也可在根目录执行 `docker compose up -d --build --wait --wait-timeout 240`。训练用NPZ未随包提供，不影响网页运行；复现实验需按研究README重新构建训练数组。

论文位于 `paper/final/ECG_AI_课程论文_完整研究版V6.docx` 和同名PDF。它以V5为底稿整合60次新研究，保留旧结果并说明新旧评价口径、患者局限与拒识取舍。

## 实际验证边界

本次交付执行ZIP CRC、逐文件SHA-256、独立解压目录启动、模型加载和真实API验证。本机使用Windows和已验证的Python 3.12依赖，不把它写成Ubuntu容器或远程服务器已经部署成功。服务器实际部署结果以执行上述命令后的输出为准。
