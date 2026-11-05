# 第二阶段 API 契约

服务默认监听 `127.0.0.1:8000`，Swagger 文档为 `/docs`。数组字段和输出示例以实际 JSON 为准；错误响应使用 `{"detail":"..."}`。

| Method | Path | 作用与约束 |
|---|---|---|
| GET | `/api/health` | 本地健康状态、已加载工件数量、教学用途标记 |
| GET | `/api/ecg/records` | 本地 `.hea/.dat/.atr` 完整记录、导联、采样率、时长、标注计数、split 与可推理原因 |
| GET | `/api/ecg/records/{record_id}` | 单记录元数据；编号须为三位且在 allowlist 内 |
| GET | `/api/ecg/window` | `record_id,start_sec,duration_sec,lead_name,max_points`；最长 30 秒、最多 18,000 点；振幅以 mV 返回 |
| GET | `/api/ecg/annotations` | `record_id,start_sec,duration_sec,task`；逐条返回原始符号、AAMI 类、注释类型和是否属于任务 |
| GET | `/api/ecg/beat` | `record_id,annotation_sample,task,lead_name`；验证 `.atr` 位置并返回 253 点原始/滤波心拍 |
| GET | `/api/models` | 两任务类别顺序、每个模型加载状态、版本、哈希、输入长度 |
| GET | `/api/models/{model_id}` | 按模型编号检查工件状态 |
| POST | `/api/inference/beat` | JSON `{record_id, annotation_sample, task, model_id}`；指定单模型真实推理 |
| POST | `/api/inference/compare` | JSON `{record_id, annotation_sample, task}`；三个工件使用相同窗口推理 |
| POST | `/api/inference/batch` | JSON `{record_id, annotation_samples, task, model_ids}`；最多 128 位置、3 模型，不接受重复项 |
| GET | `/api/ecg/playback/segment` | 记录、时间窗、任务、导联和重复 `model_ids` 查询项；返回波形、标注与批处理预测 |

## 输入验证与状态码

- `404`：不存在于本地完整记录 allowlist 的编号或未知模型。
- `409`：标注不属于所选任务、记录没有模型资格，或该导联不是 MLII。
- `422`：字段格式错误、时间窗越界、不是专家心拍位置、滤波保护区/窗口边界/重复注释等预处理规则拒绝。
- `503`：目标模型工件缺失、加载失败或推理输出无效。

模型推理只允许现有四十四记录实验清单及 MLII 导联。预测输出包含 expert label 仅用于事后核对；该字段不会进入模型特征。所有概率都是未临床校准的模型输出。
