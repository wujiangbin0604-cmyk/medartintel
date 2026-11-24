# 服务器更新包与历史记录

## 2026-11-19 节律融合与可靠性实验室

推荐使用根目录 [SERVER_UPDATE.md](../../SERVER_UPDATE.md) 中的GitHub更新命令，兼容旧ZIP解压目录与Git克隆。更新前验证完整运行文件，备份将覆盖的代码与报告，保留 `.env`、原始ECG、原六模型和游戏数据。

本版更新包含独立目录中的60个新研究checkpoint及对应结果；原正式checkpoint仍不允许被增量包覆盖。目标目录已有不同哈希的同名研究checkpoint时也会拒绝覆盖。GitHub官方快照下载中断会最多重试两次，验证通过前不复制项目文件。

需要自行制作增量ZIP时，在最新且已验证的完整工作区运行：

```bash
python deploy/update/build_update.py --output releases/ECG-AI_Server_Update_20261119.zip
python -m unittest discover -s deploy/update/tests -v
```

增量包会要求目标已有未包含在包中的原运行文件，缺失或哈希不符时停止；更新较早版本服务器时优先使用GitHub完整运行清单更新入口。

## 2026-11-09 网站文案更新（历史说明）

简化网站页脚、欢迎弹窗、推理结果、回放提示、游戏、实验页面及图库报告的展示文案。原始ECG、六个模型、实验指标、研究报告、图表、游戏规则和运行配置沿用现有版本。

## 使用服务器更新包

将 `ECG-AI_Server_Update_20261109.zip` 上传到服务器，例如 `/tmp/`：

```bash
cd /tmp
unzip ECG-AI_Server_Update_20261109.zip -d ecg-ai-update-20261109
cd ecg-ai-update-20261109
# 将 /实际项目目录/ecg-ai 换成现有项目根目录
sudo bash update-server.sh /实际项目目录/ecg-ai
```

项目根目录内应有 `web/backend/production.py` 和 `deploy/ubuntu22/compose.yaml`。可先只做校验：

```bash
python3 apply_update.py /实际项目目录/ecg-ai --check
```

脚本先核验更新文件 SHA256，以及更新后完整运行清单中的每一个文件，自动备份将被覆盖的文件，再覆盖页面、相关文案源码及部署完整性清单，最后沿用现有 Ubuntu Docker Compose 配置重建并启动服务。首次重建需要服务器能访问原有镜像与依赖源。

备份位于项目目录的同级隐藏目录 `.<项目目录名>-update-backups/时间戳/`。更新包不包含 `.env`、SQLite 游戏记录、模型权重或 ECG 原始数据。更新过程中不删除 Docker 数据卷。

更新完成后继续访问原地址：

[http://47.83.150.55:8000/dashboard](http://47.83.150.55:8000/dashboard)

如果浏览器仍显示旧文案，请按 Ctrl+F5 强制刷新。

## 修复旧更新包缺失 deploy/local.py

旧服务器使用早期 Ubuntu 包时，第一次增量包漏带 `deploy/local.py`，会在 Docker 构建时报告 `Missing/invalid artifact: deploy/local.py`。修正版按完整运行清单选择部署脚本，已包含该文件；覆盖之前会检查所有运行文件，发现缺失或哈希不符时停止。

已覆盖旧更新包的服务器可直接补齐已发布提交中的文件后继续部署：

```bash
cd /root/ecg-ai &&
curl -fL --retry 3 --connect-timeout 15 \
  https://raw.githubusercontent.com/wujiangbin0604-cmyk/medartintel/f39571093bdb92e97da693d63d4e45b3dc1d1e4b/deploy/local.py \
  -o deploy/local.py &&
python3 deploy/ubuntu22/verify_bundle.py --files-only &&
bash deploy/ubuntu22/deploy.sh
```

## 制作与检查更新包

在项目根目录使用 Python 3.12 执行：

```bash
python deploy/update/build_update.py
python -m unittest discover -s deploy/update/tests -v
```

打包直接根据 `bundle_manifest.json` 选取运行代码、前端构建和全部部署脚本，不依赖 Git 工作区是否存在未提交修改。

## 从 GitHub 更新

已有 Git 克隆且工作区无本地改动时，也可以在服务器项目根目录执行：

```bash
git pull --ff-only origin main
sudo bash deploy/ubuntu22/deploy.sh
```
