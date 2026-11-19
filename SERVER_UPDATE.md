# 从 GitHub 更新 ECG-AI 服务器

本次更新加入节律融合与可靠性实验室，以及60个已完成的研究模型和结果。服务器无需训练，也无需安装Node.js。原始ECG、原六模型、`.env` 和现有游戏数据卷保留。

## 已有服务器：兼容 Git 克隆和旧 ZIP 解压目录

以下使用现有部署文档中的 `/root/ecg-ai`。项目在其他位置时，替换两处目录；进入包含 `web/backend/production.py` 和 `deploy/ubuntu22/compose.yaml` 的根目录。

```bash
cd /root/ecg-ai
curl -fL --retry 3 --connect-timeout 20 \
  https://raw.githubusercontent.com/wujiangbin0604-cmyk/medartintel/main/deploy/update/from_github.py \
  -o /tmp/ecg-ai-from-github.py
sudo python3 /tmp/ecg-ai-from-github.py /root/ecg-ai
sudo bash deploy/ubuntu22/deploy.sh
```

更新器先将 `main` 解析为具体commit，再下载该commit快照，校验更新后的完整运行清单，备份将覆盖的文件，然后复制更新。原始ECG或原六模型缺失/哈希不符时停止，不覆盖它们。新增研究checkpoint使用独立目录；同目录已有不同checkpoint时也停止。

备份在项目同级 `.<项目目录名>-update-backups/时间戳/`。更新不执行 `docker compose down -v`，不改Compose项目名，不替换已有 `.env`。`deploy.sh`复用原端口和游戏数据卷，重建镜像并核验六模型参考预测、研究模型及API。

只检查、不改项目文件：

```bash
sudo python3 /tmp/ecg-ai-from-github.py /root/ecg-ai --check
```

需要固定发布版本时，在更新器命令末尾加 `--ref <完整commit SHA>`。本次实际验证边界见 [发布验证记录](deploy/validation/20261119/README.md)。

## 使用 Git 管理且工作区干净的服务器

确认没有需要保留的本地源码改动后，二选一使用下面的方法；不要在有本地修改时强制reset。

```bash
cd /root/ecg-ai
git status --short
git pull --ff-only origin main
sudo bash deploy/ubuntu22/deploy.sh
```

如果之前用上面的覆盖更新器更新过同一个Git目录，Git可能显示源码已改变；继续使用覆盖更新器即可，不需要清理源码或游戏卷。

## 更新后验收

```bash
cd /root/ecg-ai
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8000/api/rhythm/summary \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("jobs",len(d["folds"]),"seeds",d["config"]["seeds"],"reliability",len(d["uncertainty"]["results"]))'
```

默认端口下，第一项应为 `status: ok`、6个原模型就绪；第二项应显示60组训练、3个种子、24组可靠性结果。如果 `.env` 配置其他端口，替换8000。

浏览器打开 `http://47.83.150.55:8000/rhythm-lab`（使用其他IP/端口时相应替换）。按Ctrl+F5刷新旧缓存。完整验收由部署脚本自动运行，也可以重跑：

```bash
sudo docker compose --env-file deploy/ubuntu22/.env \
  --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml \
  exec -T ecg-ai python deploy/ubuntu22/verify_bundle.py --api http://127.0.0.1:8000
```

## 全新下载并本地运行

```bash
git clone https://github.com/wujiangbin0604-cmyk/medartintel.git
cd medartintel
```

Windows安装64位Python 3.12后执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1 -CheckOnly
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

访问 `http://127.0.0.1:8000/rhythm-lab`。首次联网安装固定CPU依赖，之后用本地数据和模型运行。Linux原生使用Python 3.12及`bash start-local.sh`；Ubuntu 22.04更适合安装Docker后运行`sudo bash deploy/ubuntu22/deploy.sh`。Windows/Linux安装Docker后也可直接`docker compose up -d --build --wait --wait-timeout 240`。

依赖与硬件范围以[本地部署说明](DEPLOY_LOCAL.md)为准。训练用大型NPZ不随运行部署包提供；它们不是网页启动依赖。
