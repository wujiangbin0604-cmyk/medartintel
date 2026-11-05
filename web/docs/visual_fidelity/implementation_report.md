# 第五阶段代码实现

2026-11-04。现有 React / Umi / Ant Design / ECharts / Motion 项目内重构，后端模型、数据和历史实验文件未修改。

| 文件 | 具体修改 |
| --- | --- |
| src/layouts/MedicalLayout.tsx | 64px 白色顶栏，模型/数据状态；212px 桌面文字菜单，64px 窄屏菜单与 Tooltip、展开行为 |
| src/components/MedicalVisuals.tsx | 心电 Logo、轻量冰蓝心脏与波形 SVG、统一双语面板标题、KPI 辅助示意图 |
| src/styles/fidelity.less | 参考稿框架比例、Dashboard 三列、工作台三列、独立横栏、等高模型卡和五档尺寸适配 |
| src/pages/dashboard/FidelityDashboard.tsx | 替换长两列首页；四 KPI、类别/计数、分区/概览、双任务四指标、六阶段流程和可展开精确表格 |
| src/components/Research.tsx | 功能图标、中文标题、英文副标题；复用现有 ECharts 管理和动画 |
| src/pages/ai-detection/index.tsx | 重排 React 区域；控制台记录/导联/任务/模型；回放独立；真实前后心拍导航；AI 检测单拍/结果分区 |
| components/BeatDetail.tsx | 单拍图改为响应式 ECharts；full/waveform/result 三种组合，保持同一 sample 和实际波形 |
| components/ECGSignal.tsx | AI 父级真实窗口 compact 模式，保留点击、标注、精确采样命中、zoom 与 RAF 游标 |
| components/ModelResults.tsx | 三卡标题、预测类别、动态概率和耗时横向分区；保持各模型自己的真实值，精确表格可展开 |
| components/PlaybackControls.tsx | 独立横栏，播放/暂停、前后心拍、停止/复位、四种速度、实际时间与进度 |
| tests/fidelity.spec.ts / phase5.spec.ts | 五尺寸视觉证据；真实图表模式、窄屏菜单、sample 一致性、三模型 API、暂停及减少动画 |

KPI 仍显示 48 条完整记录、100115 条四类有效心拍、6 个已载入工件及历史 test CNN Macro-F1；参考图中的 100/30000/92.6% 未进入真实数据。小型 KPI SVG 为 aria-hidden 的装饰示意，不作为实验曲线。

动效复用上一阶段的统一 Motion/RAF，不增加依赖。图表更改后平滑过渡；模型卡片按真实响应更新；减少动画遵循系统偏好。详细耗时与失败记录保留在日志中。
