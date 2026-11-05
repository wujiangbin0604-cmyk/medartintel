# ECG-AI · Ubuntu 22.04 64 位部署

此包包含最新欢迎引导、Heartbeat Hunter、ECG 分析、AI 推理与科研页面。适用于 **Ubuntu 22.04 x86_64/amd64** 服务器，使用 Docker Compose + CPU 推理，前端已构建，不需要在服务器安装 Node.js，也不需要 GPU。

当前模型的 Python 主版本为 3.12，scikit-learn 为 1.9.1。容器使用 `python:3.12-slim-bookworm`（Debian 12 用户空间），在 Ubuntu 22.04 主机上运行；不使用 Ubuntu 默认 Python 3.10，也不复制 Windows `.venv`。为保持已保存模型兼容，锁定科学计算与推理依赖，PyTorch 使用同版本 `2.14.1+cpu`。不要随意改成其他 sklearn 版本。

已处理普通 `http://服务器IP` 下浏览器 randomUUID 不可用的情况，使用 getRandomValues 生成标准 UUID v4；游戏不要求必须以 localhost 方式访问。

建议配置：2 核 CPU / 4 GB 内存起，建议至少 8 GB 可用磁盘用于镜像、依赖与数据。首次构建需要联网访问 Docker Hub、Docker 官方仓库、PyPI 和 PyTorch CPU 索引；这不是完全离线镜像包。

## 1. 上传和解压

将 `ECG-AI_Ubuntu22_amd64.zip` 上传到服务器，例如 `/home/ubuntu/`。可选一起上传 `.zip.sha256` 核验文件。

Windows PowerShell 上传示例，将用户、IP 换成你的实际值：

```powershell
scp "E:\医学人工智能\releases\ECG-AI_Ubuntu22_amd64.zip" ubuntu@服务器IP:~/
scp "E:\医学人工智能\releases\ECG-AI_Ubuntu22_amd64.zip.sha256" ubuntu@服务器IP:~/
```

SSH 登录 Ubuntu 后执行：

```bash
sudo apt update
sudo apt install -y unzip
cd ~
# 如果上传了校验文件，先检查上传完整性：
sha256sum -c ECG-AI_Ubuntu22_amd64.zip.sha256
unzip ECG-AI_Ubuntu22_amd64.zip
cd ecg-ai
```

ZIP 使用 `ecg-ai/` 单层根目录、UTF-8 路径、Linux `/` 分隔符，Shell 脚本为 LF 换行。上传后不要只提取 web/frontend/dist；模型、原始数据和后端必须一起保留。

## 2. 安装 Docker（首次部署）

```bash
sudo bash deploy/ubuntu22/install-docker.sh
```

脚本按 Docker 官方 Ubuntu apt 仓库安装 Docker Engine 和 Compose plugin，检查 Ubuntu 22.04 / amd64。若已有可用 Docker + Compose，则直接复用。若发现冲突的旧容器组件，会明确停止，不自动卸载服务器已有软件。

官方依据：[Docker Ubuntu 安装文档](https://docs.docker.com/engine/install/ubuntu/)。

## 3. 一键构建与后台启动

```bash
sudo bash deploy/ubuntu22/deploy.sh
```

脚本自动建立 `.env`、构建镜像、后台启动并等待健康检查，再验证文件哈希、48 条真实记录、科研接口、游戏及六个模型的 18 条参考预测。前端与 API 在同一个端口提供，不需要另外开开发服务器。

部署完成后打开：

```text
http://服务器IP:8000/
```

云服务器安全组需要允许 TCP 8000。容器默认映射 `0.0.0.0:8000`；如果端口有冲突，可以先复制配置再修改：

```bash
cp deploy/ubuntu22/.env.example deploy/ubuntu22/.env
nano deploy/ubuntu22/.env
# 例如改为 ECG_HTTP_PORT=8080
sudo bash deploy/ubuntu22/deploy.sh
```

如果已经有 `.env`，只需编辑现有文件，不要用 cp 覆盖自己的配置。仅供内网或个人使用时可将 `ECG_BIND_HOST` 改为 `127.0.0.1`，再通过自己的反向代理或 SSH 隧道访问。

## 4. 验收与日常操作

在解压后的 `ecg-ai` 目录执行：

```bash
# 状态，正常应显示 Up / healthy
sudo docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml ps

# 查看日志，Ctrl+C 只退出日志查看，不停止服务
sudo docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml logs -f --tail=100

# 再次执行完整部署自检
sudo docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml exec -T ecg-ai python deploy/ubuntu22/verify_bundle.py --api http://127.0.0.1:8000

# 重新启动
sudo docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml restart

# 停止；不删除游戏记录卷
sudo docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml down

# 停止后重新启动
sudo docker compose --env-file deploy/ubuntu22/.env --project-directory deploy/ubuntu22 -f deploy/ubuntu22/compose.yaml up -d --wait
```

本机健康接口（按实际对外端口修改）：

```bash
curl -fsS http://127.0.0.1:8000/api/health
```

应包含 `status: ok`、`models_loaded: 6`、`models_total: 6`。Docker HEALTHCHECK 同时检查六个模型是否加载，避免只因页面可打开就误认为 AI 正常。

容器随 Docker 开机启动。SQLite 游戏记录保存在命名卷 `ecg-ai_game_data`，普通 restart/down 不会丢失；不要使用 `down -v`，该参数会删除游戏记录卷。旧 Windows 演示记录不在部署包中，新服务器从空的匿名游戏记录开始。欢迎引导 localStorage 则由各访问者浏览器保存。

## 5. 包内内容与精简范围

包含：

- 全部 48 条 MIT-BIH 原始记录（hea/dat/atr）和源校验信息。
- N/V 与 N/S/V/F 的 LR、RF、CNN 正式模型与训练摘要。
- 推理用 normalization、processing_config 和 split_manifest。
- Dashboard、错误分析所需既有结果 CSV、报告和全部科研图库。
- 后端、前端源码、已构建 dist、62 个游戏关卡。
- 最新游戏/欢迎文档及截图、部署脚本和哈希清单。

不包含 Windows 虚拟环境、node_modules、缓存、临时日志、旧 SQLite 游戏记录、训练用大型 NPZ 和 metadata.csv。上述精简不影响网页运行；这是运行部署包，不是完整训练数据备份。训练/完整离线实验重算以及读取 val.npz 的旧研究验证脚本需要原始工作区中的额外训练文件。

部署自检使用已经导出的 6 个真实验证心拍，核对 18 个模型预测及概率（容差 1e-5），不需要携带训练 NPZ，也不会拟合或重训模型。自检会生成一个隔离匿名玩家的空选择演示成绩，不影响真实玩家个人记录。

## 6. 常见问题

- **Docker Hub / pip / PyTorch 下载超时**：首先检查服务器到这些官方仓库的网络连通性。构建日志会显示具体失败的主机。该 ZIP 没有包含几百 MB 的 Python 安装轮子或完整 Docker 镜像。
- **页面打开但 AI 不可用**：查看 logs 中具体的模型加载错误，确认六个模型均加载。使用随包的固定依赖，不要改用 Ubuntu 默认 Python 或随意升级 sklearn。
- **外网打不开、本机 curl 正常**：检查云安全组的 TCP 对外端口和 `.env` 的 `ECG_BIND_HOST/ECG_HTTP_PORT`。Docker 端口映射与 ufw 的交互以官方文档为准，不能只凭 ufw 状态判断容器端口是否对外开放。
- **想用 80 端口**：将 `.env` 的 ECG_HTTP_PORT 改成 80 后重新执行 deploy.sh，确保该端口未被已有 Nginx/Apache 占用。
- **已有域名/HTTPS**：让现有反向代理转发到本服务即可，前端 API 使用相对路径。此包没有代替你修改现有域名和证书。
- **访客范围**：沿用本地课程平台，没有新增账号认证。公开服务器的访问范围请按你自己的部署用途配置。
- **ARM64 服务器**：此包按 amd64 固定并检查；不要将它当作已验证的 ARM64 方案。

## 7. 验证范围与限制

制作包时已验证官方索引中全部 63 个固定依赖的 Linux CPython 3.12 兼容 wheel，包含 CPU PyTorch 并核对 Linux 依赖闭包；结果见 `linux_dependency_check.json`。部署 Shell 语法通过本地解析器检查，ZIP 有 CRC 和 SHA-256 校验。

会对解压目录进行独立启动与真实 API 自检，具体结果随 ZIP 一起提供 `releases/package_validation.json`。这一步在当前 Windows Python 环境执行，以检查打包依赖文件是否齐全；当前机器未安装可用 Docker/WSL，不能把它宣称为已经在 Ubuntu 服务器上执行过 docker build。Ubuntu 上的实际安装、镜像构建与 18 条预测检查由 deploy.sh 执行。

资料：[Docker Ubuntu 22.04 支持](https://docs.docker.com/engine/install/ubuntu/)、[scikit-learn 模型持久化版本要求](https://scikit-learn.org/stable/model_persistence.html)、[PyTorch 官方 CPU 安装索引](https://download.pytorch.org/whl/cpu/torch/)。
