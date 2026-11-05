# 第二阶段测试与验收

## 安装和本地启动

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r web\backend\requirements.txt
cd web\frontend
npm install
```

终端一启动后端：

```powershell
cd E:\医学人工智能
.\.venv\Scripts\python.exe -m uvicorn web.backend.app:app --host 127.0.0.1 --port 8000
```

终端二启动前端：

```powershell
cd E:\医学人工智能\web\frontend
npm run dev
```

访问 `http://127.0.0.1:8001/ai-detection`。启动命令、端口与 Playwright 配置一致。

## 自动检查

```powershell
cd E:\医学人工智能
.\.venv\Scripts\python.exe -m pytest -q web\backend\tests
cd web\frontend
npm run typecheck
npm run build
npm run test:e2e
```

Playwright 配置会启动本地 FastAPI 与 Umi Max 服务，测试实际记录 200 的标注选择、CNN/RF/LR 模型切换、同拍三模型比较、任务切换及历史回放交互。配置使用 Playwright `channel: "chrome"`，因此本机需安装 Google Chrome；也可改为已安装的 `msedge` 通道。不依赖另行下载 Playwright Chromium。

## 保存模型一致性核验

```powershell
cd E:\医学人工智能
.\.venv\Scripts\python.exe -m web.backend.validate_saved_models --samples-per-task 100
```

该脚本从 `val.npz` 按类别确定性选取样本，将实际 WFDB/`.atr` 位置送入线上同一服务，再与已有验证预测 CSV 比较输入向量、预测类及各类输出概率。它不会读取正式测试 NPZ，也不更改模型、划分和既有预测文件。逐拍明细和汇总落在 `web/results/phase2_validation/`。
