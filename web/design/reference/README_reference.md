# ECG-AI Ant Design Pro 视觉对照包

本包用于 Codex 的浅色医学科技风前端重构。解压到项目 `web/design/reference/`，保留 `references/` 子目录。

## 目标
- 01_dashboard_target.png：Dashboard 桌面目标（设计参考，数据数值仅占位示意）
- 02_ecg_workspace_target.png：ECG 波形工作台布局目标
- 03_ecg_analysis_target.png：ECG 主工作台另一版布局参考
- 04_model_comparison_target.png：AI 智能检测和三模型结果对比目标
- 05_current_implementation_screenshot.png：用户当前 745×671 截图，供定位当前差距；不是目标界面

## 使用规则
1. 正式参考仅为 01-04，05 是反例。
2. 概念图中的记录编号、心拍数量、标签、预测概率和模型性能均不得直接写死，真实平台的数据必须来自项目文件或 API。
3. 使用 React/Ant Design Pro/ECharts 实现可操作 UI，而非展示图片作为网页。
4. 对照 1672×941 原始参考图，另核对 1366×768、1440×900、1920×1080、745×671。
5. 如果现有组件/配色与参考冲突，以参考视觉层次为目标，但不修改真实数据或模型接口语义。
