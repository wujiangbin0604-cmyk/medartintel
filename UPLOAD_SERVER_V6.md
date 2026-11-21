# ECG-AI V6 完整包上传与启动

**Linux修复入口（2026年11月21日）：** 原20261119包的模型注册表路径存在跨平台读取问题。已上传旧包时，先按[Linux修复说明](SERVER_LINUX_FIX.md)应用随附的ecg_v6_linux_fix.py，再构建镜像。新部署可使用ECG-AI_Full_Server_V6_LinuxFix_20261121.zip。下文原包准备流程仍可用于原ZIP的完整性检查。

发布日：2026年11月19日。适用于 Ubuntu 22.04、amd64/x86_64、Docker CPU 部署。ZIP 是完整网页运行包，包含48条原始记录、6个原生产模型、60个研究检查点、预构建前端、结果、部署脚本以及 V6 论文 Word/PDF。服务器无需训练或安装 Node.js。第一次 Docker 构建需要联网下载基础镜像与固定依赖；ZIP 不含 Docker 镜像。

2026年11月21日修正执行方式：准备步骤改为独立Python脚本，逐步输出并保存日志。完整解压目录可重复校验。原ZIP及校验值不变；使用本说明和随附的ecg_v6_prepare.py替换原ZIP内旧说明的第2步。

## 1 在本地 PowerShell 上传

先进入 ZIP 所在文件夹，再执行。以下服务器地址沿用现有项目文档。

```powershell
Get-FileHash .\ECG-AI_Full_Server_V6_20261119.zip -Algorithm SHA256
scp .\ECG-AI_Full_Server_V6_20261119.zip .\ECG-AI_Full_Server_V6_20261119.zip.sha256 root@47.83.150.55:/tmp/
scp .\ecg_v6_prepare.py root@47.83.150.55:/tmp/
ssh root@47.83.150.55
```

## 2 在服务器校验并解压到新目录

先上传随附脚本，再执行下面命令。交互式SSH中不启用set -e，脚本失败以非零退出码报告，不退出会话。原/root/ecg-ai保留；新目标才解压，已有目标则校验全部文件，不覆盖。直接复制代码块，不在每行末尾加反斜杠，也不要复制HTML实体&#x20;。

```bash
set +e
set +u
set +o pipefail
python3 -u /tmp/ecg_v6_prepare.py --log /tmp/ecg-v6-prepare.log
printf 'prepare_exit=%s\n' "$?"
```

脚本内置原V6 ZIP的SHA-256，随后检查ZIP CRC及全部1294个交付文件。看到PASS: complete package verified.和prepare_exit=0才进入第3步。错误同时输出到终端和/tmp/ecg-v6-prepare.log。若仍断开，重新连接后执行以下命令读取最后阶段：

```bash
tail -n 80 /tmp/ecg-v6-prepare.log
```

已有目录不完整或文件改动时，脚本保留它们并报错。可用新目录重试：

```bash
python3 -u /tmp/ecg_v6_prepare.py --target /root/ecg-ai-v6-20261121-retry --log /tmp/ecg-v6-prepare.log
```

后续进入目录时，以成功输出的PROJECT=路径为准。

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
