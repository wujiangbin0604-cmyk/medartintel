# ECG-AI Ant Design Pro 视觉对照包

本包用于 Codex 的浅色医学科技风前端重构。解压到项目 `web/design/reference/`，保留 `references/` 子目录。

## 目标
- 01_dashboard_target.png：Dashboard桌面目标，图中数值为布局占位数据
- 02_ecg_workspace_target.png：ECG 波形工作台布局目标
- 03_ecg_analysis_target.png：ECG 主工作台另一版布局参考
- 04_model_comparison_target.png：AI 智能检测和三模型结果对比目标
- 05_current_implementation_screenshot.png：用户当前745×671截图，用于对照现有界面与目标的差距

## 使用规则
1. 01-04为目标参考，05为现有界面对照。
2. 平台的记录编号、心拍数量、标签、预测概率和模型性能从项目文件或API读取。
3. 使用React/Ant Design Pro/ECharts实现可操作UI。
4. 对照 1672×941 原始参考图，另核对 1366×768、1440×900、1920×1080、745×671。
5. 组件与配色按参考视觉层次调整，数据和模型接口沿用现有语义。
