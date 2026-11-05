# 第四阶段交互矩阵

| 用户操作 | 实际状态变化 | 实现 | 优先级 |
| --- | --- | --- | --- |
| 侧栏悬停/收起 | 图标与背景反馈、宽度平滑变化、图表自动 resize | MedicalLayout / ResizeObserver | P0 |
| 导航切换 | 共享高亮、退出与进入、保留筛选与滚动位置 | AnimatePresence / sessionStorage | P0 |
| KPI 加载/变化 | 真实数值过渡；Tooltip 解释；点击进入模块 | AnimatedMetric | P1 |
| 点击类别扇区/表格/按钮 | 环形中心、数量柱图和分区图同步 | DashboardView | P1 |
| 选择任务/模型/指标 | 模型图、类别指标与矩阵同步，系列显隐 | DashboardView / ECharts | P1 |
| 工作流节点点击 | 展开阶段说明、连接对应模块 | workflow-nodes | P2 |
| 读取记录 | 骨架之后由左向右显示真实波形 | ECGSignal / API | P0 |
| 鼠标查看波形 | 十字线、时间、电压、专家标签 Tooltip | ECharts axisPointer | P0 |
| 点击真实标注 | 选中区域、参考线、单次光环、详情和局部波形切换 | ECGSignal / BeatDetail | P0 |
| 查看心拍细节/返回 | 展开真实单拍窗；不拉伸静态图片 | beat-focus | P0 |
| 滚轮/框选/拖拽/重置 | 视图缩放、标注坐标一致、手动操作暂停回放 | dataZoom | P0 |
| 心拍类别筛选 | 对应标注强调，其它类别淡化，计数同步 | classFocus | P1 |
| 真实推理 | 请求期间 Loading，响应后概率呈现，失败有提示 | API + request cancellation | P0 |
| 选择模型 | 保留同一心拍，当前卡片强调，其它模型可见 | ModelResults / modelId | P0 |
| 三模型比较 | 真实响应后呈现三个结果及精确表格 | ModelResults | P0 |
| 点击类别概率 | 三个模型同类别同步强调和差异说明 | ProbabilityBar / focus | P0 |
| 播放/暂停/继续 | RAF 驱动、独立 Canvas 游标、滑动真实窗口 | PlaybackClock | P0 |
| 倍速/seek/重启 | 0.5/1/2/4 倍，基于实际时间锚点，无累计帧误差 | PlaybackClock | P0 |
| 经过真实标注 | 当前详情、真实缓存预测、计数与历史轨迹同步 | playbackSegment | P0 |
| 暂停后缩放 | 保持当前心拍与时钟，手动查看不被自动跟随抢回 | onUserZoom | P0 |
| 混淆矩阵悬停/点击 | 行列强调；打开真实保存样本与 ECG 入口 | Research / ErrorCases | P1 |
| 错误方向点击 | 按模型、真实类别和预测类别取已有样本 | research/errors | P1 |
| 患者热力图点击 | 显示真实支持量；仅 test 受试者显示已有 test 指标 | Generalization Drawer | P1 |
| 权重策略切换 | Validation Macro-F1、Accuracy、类别 Precision/Recall、预测分布更新 | weight_classes / weights CSV | P1 |
| 图库筛选/搜索 | 保留条件、卡片重排与进入、每页 12 张缩略图 | Gallery / MotionCard | P1 |
| 图库大图/键盘/缩放 | 左右键、上一张下一张、缩放、说明折叠、返回实验 | Ant Modal / local selection | P1 |
| 答辩上/下一步 | 八步手动引导、重点说明柔和切换、真实模型调用 | PresentationDemo | P1 |
| 暂停答辩/全屏/退出 | 阻止下一步并暂停时钟，继续后恢复；浏览器全屏 | demoPaused | P0 |
| 减少动画/系统偏好 | 保持可读性和功能，关闭非必要动效 | AnimationProvider | P0 |

## 验证证据

- 后端：18 passed。
- 开发 E2E：1 skipped / 15 passed (5.1m)。
- 独立生产 E2E：1 passed (16.7s)。
正常流程使用真实 API；延迟和故障注入仅用于验证加载、超时、缺图和重试，不作为医学数据。

## 范围边界

LR/RF 没有逐 Epoch 损失日志，所以训练曲线明确展示已保存 CNN 日志；不伪造其他模型曲线。错误列表只展示原 test 保存预测，最多 20 条；新跳转后的实际推理单独执行。患者在 train/val 分区时不会生成不存在的 test 指标。
