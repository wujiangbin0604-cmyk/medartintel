# 第四阶段视觉审查

参考：用户提供的三张浅色医学科技风页面。使用真实 React、ECharts 和本机接口实现；参考图不是背景，不用其示例数值。

## 发现并修复

1. 原深蓝顶栏与横向导航改为白色顶栏、浅蓝可收起侧栏，内容保留真实数据来源。
2. 旧页面局部样式覆盖新主题：用平台作用域规范优先级，统一类别颜色与背景。
3. LESS 对最后一个自定义属性缺少分号报错：补齐分号，实际编译与构建后再运行。
4. 初次 Motion 依赖预构建与记录扫描较慢：等待真实标题和 API，不截打包页或骨架。
5. 完整截图时滚动位置导致固定导航出现在图中部：截图前回到页面顶端。
6. 模型卡片过渡未结束就截图：等待请求和动效稳定；保持按模型对齐。
7. 人工估算 ECG 像素坐标不可靠：测试改用 ECharts 实际绘图坐标，并验证返回的样本位置与时间。
8. 原图库直接加载科研大图：增加保持比例的缓存缩略图，展示与下载原图分开。
9. 系统减少动画在运行时切换未同步：改为原生 matchMedia 订阅，同时关闭 Ant Design 非必要过渡；已验证三级强度、系统覆盖及图库键盘操作。
10. 波形轴提示可能落到邻近采样点：使用实际标注像素近邻命中并指定散点 seriesIndex。生产测试等待图表布局稳定后原生悬浮/点击，确认样本 487 与 1.353 s，且不触发不适用的自动推理。

## 审查项目

1366×768、1440×900、1920×1080：动画结束布局、中文可读性、卡片高度、波形面积、表格局部横向滚动、body 横向溢出、未捕获异常和失败资源。1366/1440 主要详情可通过抽屉访问，1920 使用右侧实时详情。

## 真实截图索引

- [ai_detection_1366x768.png](screenshots/phase4/ai_detection_1366x768.png)
- [ai_detection_1440x900.png](screenshots/phase4/ai_detection_1440x900.png)
- [ai_detection_1920x1080.png](screenshots/phase4/ai_detection_1920x1080.png)
- [beat_selected_1366x768.png](screenshots/phase4/beat_selected_1366x768.png)
- [beat_selected_1440x900.png](screenshots/phase4/beat_selected_1440x900.png)
- [beat_selected_1920x1080.png](screenshots/phase4/beat_selected_1920x1080.png)
- [comparison_1366x768.png](screenshots/phase4/comparison_1366x768.png)
- [comparison_1440x900.png](screenshots/phase4/comparison_1440x900.png)
- [comparison_1920x1080.png](screenshots/phase4/comparison_1920x1080.png)
- [dashboard_1366x768.png](screenshots/phase4/dashboard_1366x768.png)
- [dashboard_1440x900.png](screenshots/phase4/dashboard_1440x900.png)
- [dashboard_1920x1080.png](screenshots/phase4/dashboard_1920x1080.png)
- [dashboard_filter_1366x768.png](screenshots/phase4/dashboard_filter_1366x768.png)
- [dashboard_filter_1440x900.png](screenshots/phase4/dashboard_filter_1440x900.png)
- [dashboard_filter_1920x1080.png](screenshots/phase4/dashboard_filter_1920x1080.png)
- [ecg_1366x768.png](screenshots/phase4/ecg_1366x768.png)
- [ecg_1440x900.png](screenshots/phase4/ecg_1440x900.png)
- [ecg_1920x1080.png](screenshots/phase4/ecg_1920x1080.png)
- [error_cases_1366x768.png](screenshots/phase4/error_cases_1366x768.png)
- [error_cases_1440x900.png](screenshots/phase4/error_cases_1440x900.png)
- [error_cases_1920x1080.png](screenshots/phase4/error_cases_1920x1080.png)
- [experiment_nsvf_1366x768.png](screenshots/phase4/experiment_nsvf_1366x768.png)
- [experiment_nsvf_1440x900.png](screenshots/phase4/experiment_nsvf_1440x900.png)
- [experiment_nsvf_1920x1080.png](screenshots/phase4/experiment_nsvf_1920x1080.png)
- [gallery_1366x768.png](screenshots/phase4/gallery_1366x768.png)
- [gallery_1440x900.png](screenshots/phase4/gallery_1440x900.png)
- [gallery_1920x1080.png](screenshots/phase4/gallery_1920x1080.png)
- [generalization_1366x768.png](screenshots/phase4/generalization_1366x768.png)
- [generalization_1440x900.png](screenshots/phase4/generalization_1440x900.png)
- [generalization_1920x1080.png](screenshots/phase4/generalization_1920x1080.png)
- [inference_loading_1366x768.png](screenshots/phase4/inference_loading_1366x768.png)
- [inference_loading_1440x900.png](screenshots/phase4/inference_loading_1440x900.png)
- [inference_loading_1920x1080.png](screenshots/phase4/inference_loading_1920x1080.png)
- [playback_1366x768.png](screenshots/phase4/playback_1366x768.png)
- [playback_1440x900.png](screenshots/phase4/playback_1440x900.png)
- [playback_1920x1080.png](screenshots/phase4/playback_1920x1080.png)
- [presentation_1366x768.png](screenshots/phase4/presentation_1366x768.png)
- [presentation_1440x900.png](screenshots/phase4/presentation_1440x900.png)
- [presentation_1920x1080.png](screenshots/phase4/presentation_1920x1080.png)

回归截图另存 screenshots/phase4/regression；没有覆盖第三阶段截图和实验结果。人工审查结合全图、局部图及 contact_*.png 拼图。

## 保留边界

长研究页需要纵向滚动；小屏不强塞三列。科研原图沿用原配色与原文。动画减少设置仍保留功能性时间推进。没有生成不存在的 CNN/RF/LR 曲线或患者指标。
