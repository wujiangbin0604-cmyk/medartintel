# ECG-AI 第二阶段架构

## 运行范围

本阶段是在现有 MIT-BIH 实验项目中增加的本地教学工作台。它不重新训练模型、不更改数据集、正式预测 CSV 或测试集结果，也不提供临床诊断能力。

```text
浏览器 (Umi Max / React / Ant Design / ECharts)
  ├─ 记录、任务、导联和历史时间窗口
  ├─ ECG 标注选择、单拍推理、三模型对比
  └─ 批量生成预测后的历史回放与形态对照
                │ /api
FastAPI 本地服务
  ├─ allowlist 读取 MIT-BIH .hea/.dat/.atr
  ├─ 复用项目 WFDB、AAMI 标签和连续滤波代码
  ├─ 训练集归一化参数 + LR/RF/CNN 保存工件
  └─ 记录来源、受试者 split、标签和模型哈希
```

## 后端模块

- `backend/app.py`：HTTP 接口、输入校验、结构化请求日志、CORS 限定本地开发源。
- `backend/ecg_service.py`：记录 allowlist、有限缓存、时间窗读取、专家标注、训练流程一致的心拍截取和实时请求内推理。
- `backend/model_registry.py`：只读加载现有六个模型工件，校验类别顺序、输入维数、LR scaler、RF 无 scaler，并返回模型 SHA-256。
- `backend/schemas.py`：限定任务、模型编号、记录编号、样本数和批处理尺寸。
- `backend/validate_saved_models.py`：只对既有验证集固定样本复算，不读取正式测试 NPZ 进行验证、挑选或调参。

## 数据和模型契约

- 记录来自 `data/mitdb/`，编号由本地同时具备 `.hea`、`.dat`、`.atr` 的文件生成 allowlist；接口不接受任意文件路径。
- 浏览可访问全部完整记录。只有纳入 44 条实验记录且包含 `MLII` 时允许模型推理；其他记录仍然可以查看波形和标注。
- 标注来自 `.atr`，AAMI 映射复用 `src.labels.AAMI_MAP`。未归类、非心拍标注只展示，不进入推理。
- 模型窗口固定为专家标注前 0.3 秒、后 0.4 秒、253 点。连续信号按项目配置进行 0.5–40 Hz 四阶 Butterworth SOS 双向滤波，并应用 5 秒边缘保护区。
- 标准化只用任务对应 `normalization.json` 中由训练数据拟合的标量均值和标准差。LR 再使用训练时保存的 `StandardScaler`；RF 不缩放；CNN 使用 CPU 推理和 Softmax 概率。
- 专家标签不参与模型输入，只作为页面展示和回顾性匹配检查字段。
- 页面显示的概率不是临床校准概率；测试 split 只标记为原实验分区，不代表独立临床验证。

## 前端模块

- `frontend/src/pages/ai-detection/`：工作台编排、时间窗和心拍选择、模型切换、回放时钟及响应式布局。
- `components/ECGWaveformChart.tsx`：ECharts 原始波形、原始标签类别标记、推理标记与播放游标。
- `components/BeatDetail.tsx`：单拍原始/训练滤波波形和单模型概率。
- `components/PredictionComparison.tsx`：三模型对同一位置的预测结果表和概率对比。
- `components/PlaybackControls.tsx`：播放、暂停、停止、倍速与时间轴 seek。
- `services/api.ts`、`types/ecg.ts`：接口客户端和字段契约。

## 只读与安全边界

数据服务只读现有 WFDB、处理配置、归一化参数和模型工件。服务不接受文件上传、路径参数、模型训练命令或参数写入。回放只处理用户选定的最多 30 秒；最多 128 个心拍 × 3 个模型。记录 102、104、107、217 等不在模型数据集中的文件会显示“仅浏览”。
