# 第四阶段动画与浅色设计

执行日期：2026-11-03。已查看用户提供的三张浅色参考图，参考布局与色彩，不使用图片中的记录数、概率或指标。原始 WFDB、六个已训练模型及正式实验结果均只读。

## Light Medical Tech

白色固定顶栏、208px 左侧导航（可收起至 72px）、浅蓝背景和柔和边框。主背景 #F7FAFF，主文字 #182B49，次文字 #64748B，边框 #E4ECF5，主色 #1677FF，青色强调 #06B6D4。心拍颜色统一为 N 蓝、S 紫、V 玫红、F 青、Q 灰，并保留文本类别、专家圆点及模型菱形等非颜色区分。

KPI 读取实际 API：48 条本地完整记录、100,115 条四分类有效心拍、6 个工件、N/V CNN 98.65% 历史 test Macro-F1。图中 44 条模型数据记录与完整 48 条目录是不同口径，页面和说明分别标识。

## 动画组件与职责

| 模块 | 实际职责 |
| --- | --- |
| src/utils/motion.tsx | 单一动画上下文、标准/完整/减少三级强度、系统偏好、统一 easing 与 duration |
| src/hooks/useReducedMotion.ts | 导出统一减少动画判断 |
| src/components/Motion.tsx | MotionCard、AnimatedMetric、ProbabilityBar、Reveal |
| src/styles/motion.less | 160ms 按钮反馈、卡片悬停、一次选中脉冲、波形裁剪绘制、减少动画覆盖 |
| src/layouts/MedicalLayout.tsx | 侧栏宽度过渡、共享选中条、AnimatePresence 页面进入退出、导航与滚动位置 |
| src/components/Research.tsx | ECharts 数据更新动画、图例选择保留、热力图行列强调和点击回调 |
| src/utils/playbackClock.ts | 基于 performance.now 的 RAF 时钟、暂停/seek/速度/页面可见性及清理 |
| ECGSignal.tsx | 实际 ECG/标注/选择区域、框选/滚轮/拖动、Canvas 游标和滑动窗口 |
| ModelResults.tsx | 三模型结果呈现、模型选择、跨模型同类别概率强调、一致性总结 |

Motion 固定为 14.9.0，安装前核实 React / React DOM peer 为 ^18 或 ^19，Remix 为可选 peer；只引入一种组件动画库。配置方法参照 [MotionConfig 官方文档](https://motion.dev/docs/react-motion-config) 和 [可访问性文档](https://motion.dev/docs/react-accessibility)。

## 时序

- 用户按压：约 120ms；悬停：160–240ms；卡片：约 280ms。
- KPI 数值：600ms，仅数值依赖变化时执行，不随普通渲染重置。
- 图表首次绘制：550ms，数据更新：450ms；选中与缩放维持真实采样坐标。
- 波形首次呈现：550ms，从左向右显示现有数据；不会重新合成信号。
- 模型结果：约 300ms，三个卡片的呈现延迟相差 90ms；不代表后端按此顺序运行。
- 概率条：450ms；数字立即显示当前返回的精确概率，条宽的中间态只用于显示，不进入导出或推理。

## 减少动画

默认标准。系统 prefers-reduced-motion 的优先级高于“完整动效”；减少模式关闭位移、数字增长、图表绘制、脉冲和非必要过渡。回放时钟与游标仍作为数据功能运行。后台页面暂停非必要时钟推进，卸载清理 RAF、事件、observer 与图表。

系统偏好使用原生 matchMedia change 实时订阅；统一同步 Ant Design motion token，避免减少动画时下拉选项被过渡状态隐藏。键盘、筛选及模态框在减少模式下仍可操作。

## 数据与状态边界

波形和预测来自既有 API。等待真实请求时保留明确加载状态；不能以固定动画时长宣告成功。切记录、导联、任务或窗口会取消旧请求。绘图调试的 data-markers 是 ECharts 实际 convertToPixel 输出，测试据此点击真实标注，不再用猜测的轴范围定位。

手动缩放会暂停正在运行的回放；内部自动跟随使用静默 dataZoom，避免反馈循环。seek 修改时钟的真实锚点，下一帧继续自新位置前进。
