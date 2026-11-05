# 本地部署与线上入口

线上工作台：[http://47.83.150.55:8000/dashboard](http://47.83.150.55:8000/dashboard)。服务器由项目维护者提供。

## 1. 下载项目

```bash
git clone https://github.com/wujiangbin0604-cmyk/medartintel.git
cd medartintel
```

仓库包含页面运行所需的前端构建、48 条原始 ECG、六个正式模型、处理参数、科研报告与图集。正常使用不需要重新下载 ECG、构建前端或训练模型。建议 2 核 CPU、4 GB 内存，安装依赖或 Docker 镜像还需数 GB 磁盘。

## 2. Windows：Python 3.12 直接运行

安装 64 位 Python 3.12（推荐 3.12.10）。在项目根目录打开 PowerShell：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

启动脚本使用 `.venv`，没有时自动创建；依赖缺失时从官方 PyPI/PyTorch CPU 索引安装。首次需要联网，完成后日常运行使用本地数据、模型和页面。虚拟环境不需要 Activate。

打开 [本地工作台](http://127.0.0.1:8000/dashboard)，按 Ctrl+C 停止。

```powershell
# 只检查文件完整性和六个模型，不启动服务
powershell -ExecutionPolicy Bypass -File .\start-local.ps1 -CheckOnly
# 8000 已被占用时换一个端口
powershell -ExecutionPolicy Bypass -File .\start-local.ps1 -Port 8002
# 修复/重新安装固定版本依赖
powershell -ExecutionPolicy Bypass -File .\start-local.ps1 -InstallDeps
```

## 3. Linux：Python 3.12 直接运行

先安装 Python 3.12 和对应的 venv 支持，再执行：

```bash
bash start-local.sh
# 可选：只检查文件和模型
bash start-local.sh --check
# 更改端口
bash start-local.sh --port 8002
```

Python 环境需要与已保存模型兼容的 scikit-learn 1.9.1、PyTorch 2.14.1；不要用 Ubuntu 22.04 默认的 Python 3.10 直接加载模型。脚本固定 Python 3.12 并复用已验证的运行依赖。Ubuntu 22.04 推荐使用下面的 Docker 方案；原生 Linux 启动脚本尚未在本机执行验证。

## 4. Docker：Windows / Linux

安装 Docker Desktop 并启用 Linux containers，或在 Linux 安装 Docker Engine + Compose plugin。镜像面向 amd64/x86_64，包含 Python 3.12 和 CPU 推理环境。

```bash
docker compose up -d --build --wait --wait-timeout 240
# 完整自检：文件哈希、48 条记录、六模型的 18 条参考预测、图集和游戏
docker compose exec -T ecg-ai python deploy/ubuntu22/verify_bundle.py --api http://127.0.0.1:8000
# 查看日志
docker compose logs -f --tail=100
# 停止
docker compose down
# 再次启动
docker compose up -d --wait --wait-timeout 240
```

默认地址为 [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)。需要调整端口时，将根目录 `.env.example` 复制为 `.env`，修改 `ECG_HTTP_PORT` 后再次运行 compose。已有 `.env` 时直接编辑原文件。游戏记录保存在命名卷，普通 `down` 会保留；`down -v` 会删除卷。

Windows 本机当前没有 Docker Engine，因此本次验证采用从 Git 提取文件后独立启动 Windows Python 服务。Linux 容器构建和健康检查由部署命令在目标环境执行。

## 5. 开发与更新

修改前端时才需要 Node.js 20+：

```bash
npm --prefix web/frontend ci
npm --prefix web/frontend run build
```

前端构建 `web/frontend/dist` 随仓库提交。修改运行文件或重新构建前端后，用 Python 3.12 重新生成完整性清单和部署包：

```bash
python deploy/ubuntu22/build_release.py
```

提交更新后的源码、前端构建和 `deploy/ubuntu22/bundle_manifest.json`。`releases/` 中的大型 ZIP 不进入 Git；本地和容器启动会核验清单，发现文件变更时会明确报出路径。

## 6. 云服务器

现有线上入口使用端口 8000。Ubuntu 22.04 新部署可按以下命令操作：

```bash
git clone https://github.com/wujiangbin0604-cmyk/medartintel.git
cd medartintel
sudo bash deploy/ubuntu22/install-docker.sh
sudo bash deploy/ubuntu22/deploy.sh
```

服务器版配置 `deploy/ubuntu22/.env` 默认绑定 `0.0.0.0:8000`，云安全组需放行 TCP 8000。详细操作见 [Ubuntu 部署指南](deploy/ubuntu22/README_UBUNTU_22.04.md)。根目录 Compose 默认只绑定本机地址，适合本地部署。
