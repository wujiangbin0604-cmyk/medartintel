# 设计稿与真实实现对照

对比图从左到右：参考稿、修改前、修改后。参考稿仅用于布局；截图和原始图片均保留，没有用图片替代网页。真实数据、字体和波形使逐像素误差不适合作为唯一评分。

## 项目总览

- 参考：../../design/reference/references/01_dashboard_target.png
- 修改前：[原图](before/dashboard_1672x941.png)
- 修改后：[原图](after/dashboard_1672x941.png)
- [并排对照](comparisons/dashboard.png)

## ECG 工作台

- 参考：../../design/reference/references/02_ecg_workspace_target.png
- 修改前：[原图](before/ecg_1672x941.png)
- 修改后：[原图](after/ecg_1672x941.png)
- [并排对照](comparisons/ecg.png)

## 同拍三模型比较

- 参考：../../design/reference/references/03_ecg_analysis_target.png
- 修改前：[原图](before/comparison_1672x941.png)
- 修改后：[原图](after/comparison_1672x941.png)
- [并排对照](comparisons/comparison.png)

## AI 智能检测

- 参考：../../design/reference/references/04_model_comparison_target.png
- 修改前：[原图](before/ai_1672x941.png)
- 修改后：[原图](after/ai_1672x941.png)
- [并排对照](comparisons/ai.png)

## 已还原与保留差异

| 页面 | 布局/交互/动画 | 仍有差异 |
| --- | --- | --- |
| Dashboard | 四 KPI、左类别/数量、中分区/概览、右双任务指标、横向流程；筛选和坐标模式均有真实状态更新 | 原图蓝色/玫红比例取决于真实数据；宏平均指标和工件数口径不同；插图是轻量 SVG，非原稿 3D 素材 |
| ECG | 控制/大波形/详情三列；独立回放和三模型；点击、模型切换、概率过渡、暂停/seek | 波形来自记录 200 的实际窗口，幅值与参考不同；保留原始/滤波双曲线；小桌面详情放在主图下并可用 Drawer |
| AI | 控制/单拍/推理结果三列、父级真实窗、下方三卡和回放 | 一致性说明在卡片下方；未增加参考图的第四个圆环卡；真实窗口设置保留在可展开项；1672×941 下回放栏需要略向下滚动，整体高度仍比参考稿长 |
| 实验 | 保留真实指标、混淆矩阵与错误样本，统一新框架 | 参考包没有对应实验页面设计，按全站 tokens 适配，不声称逐图还原 |

小屏（745×671）采用纵向操作流程，不缩小整个桌面网页。截图同时保留 full 后缀完整页面；较长科研页面需要纵向滚动。

## 五尺寸证据

- 1672×941：[项目总览](after/dashboard_1672x941.png) · [ECG 工作台](after/ecg_1672x941.png) · [同拍三模型比较](after/comparison_1672x941.png) · [AI 智能检测](after/ai_1672x941.png) · [实验](after/experiments_1672x941.png)
- 1920×1080：[项目总览](after/dashboard_1920x1080.png) · [ECG 工作台](after/ecg_1920x1080.png) · [同拍三模型比较](after/comparison_1920x1080.png) · [AI 智能检测](after/ai_1920x1080.png) · [实验](after/experiments_1920x1080.png)
- 1440×900：[项目总览](after/dashboard_1440x900.png) · [ECG 工作台](after/ecg_1440x900.png) · [同拍三模型比较](after/comparison_1440x900.png) · [AI 智能检测](after/ai_1440x900.png) · [实验](after/experiments_1440x900.png)
- 1366×768：[项目总览](after/dashboard_1366x768.png) · [ECG 工作台](after/ecg_1366x768.png) · [同拍三模型比较](after/comparison_1366x768.png) · [AI 智能检测](after/ai_1366x768.png) · [实验](after/experiments_1366x768.png)
- 745×671：[项目总览](after/dashboard_745x671.png) · [ECG 工作台](after/ecg_745x671.png) · [同拍三模型比较](after/comparison_745x671.png) · [AI 智能检测](after/ai_745x671.png) · [实验](after/experiments_745x671.png)
