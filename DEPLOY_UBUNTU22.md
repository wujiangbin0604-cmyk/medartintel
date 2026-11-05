# ECG-AI Ubuntu 22.04 64 位部署

线上体验：[ECG-AI 工作台](http://47.83.150.55:8000/dashboard)。本地 Windows/Linux/Docker 启动见 [本地部署说明](DEPLOY_LOCAL.md)。

从 GitHub 部署可先执行 `git clone https://github.com/wujiangbin0604-cmyk/medartintel.git`、`cd medartintel`，再运行下方安装与部署命令；无需先上传 ZIP。

本包适用于 Ubuntu 22.04 **amd64/x86_64**。已包含前端构建、48 条 ECG 原始记录、6 个模型、62 个游戏关卡及科研页面资源。

在 Ubuntu 上传并解压后：

```bash
cd ecg-ai
sudo bash deploy/ubuntu22/install-docker.sh
sudo bash deploy/ubuntu22/deploy.sh
```

默认访问 `http://服务器IP:8000/`；云安全组放行 TCP 8000。首次部署需要联网下载 Docker 和 Python 依赖。已有 Docker/Compose 会直接复用。

完整上传、端口修改、日志、停止/重启、数据保存和验证边界见：

[完整部署说明](deploy/ubuntu22/README_UBUNTU_22.04.md)

本包不携带 Windows 虚拟环境、node_modules、训练 NPZ 或旧的个人游戏记录。容器固定 Python 3.12 与原模型依赖，CPU 推理，不需要 GPU 或服务器 Node.js。制作端没有可运行的 Docker/WSL，Linux 构建需由服务器执行；随包自检会核验真实 ECG、六模型及 18 条参考预测。
