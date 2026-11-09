# 2026-11-09 网站最终文案更新

清理网站页脚、欢迎弹窗、推理结果、回放提示、游戏、实验页面及图库报告展示中的免责声明和防御性表述。原始 ECG、六个模型、实验指标、原始研究报告、图表、游戏规则和运行配置沿用现有版本。

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

脚本先核验更新文件 SHA256，自动备份将被覆盖的文件，再覆盖页面、相关文案源码及部署完整性清单，最后沿用现有 Ubuntu Docker Compose 配置重建并启动服务。首次重建需要服务器能访问原有镜像与依赖源。

备份位于项目目录的同级隐藏目录 `.<项目目录名>-update-backups/时间戳/`。更新包不包含 `.env`、SQLite 游戏记录、模型权重或 ECG 原始数据。更新过程中不删除 Docker 数据卷。

更新完成后继续访问原地址：

[http://47.83.150.55:8000/dashboard](http://47.83.150.55:8000/dashboard)

如果浏览器仍显示旧文案，请按 Ctrl+F5 强制刷新。

## 从 GitHub 更新

已有 Git 克隆且工作区无本地改动时，也可以在服务器项目根目录执行：

```bash
git pull --ff-only origin main
sudo bash deploy/ubuntu22/deploy.sh
```
