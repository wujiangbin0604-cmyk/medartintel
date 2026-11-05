from pathlib import Path
import json
import re

WEB=Path(__file__).parent
DOCS=WEB/'docs'
def read(name):
    path=DOCS/name
    return path.read_text(encoding='utf-8-sig',errors='replace') if path.exists() else ''
def data(name):
    return json.loads(read(name)) if read(name) else {}
def write(name,text):
    (DOCS/name).write_text(text.strip()+'\n',encoding='utf-8')
def summary(name):
    text=read(name)
    return ' / '.join(re.findall(r'^\s*(\d+ (?:passed|failed|skipped)(?: \([^\r\n]+\))?)',text,re.M)) or '尚未取得最终测试汇总'

write('phase4_animation_design.md', '''# 第四阶段动画与浅色设计

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
''')

rows=[
('侧栏悬停/收起','图标与背景反馈、宽度平滑变化、图表自动 resize','MedicalLayout / ResizeObserver','P0'),
('导航切换','共享高亮、退出与进入、保留筛选与滚动位置','AnimatePresence / sessionStorage','P0'),
('KPI 加载/变化','真实数值过渡；Tooltip 解释；点击进入模块','AnimatedMetric','P1'),
('点击类别扇区/表格/按钮','环形中心、数量柱图和分区图同步','DashboardView','P1'),
('选择任务/模型/指标','模型图、类别指标与矩阵同步，系列显隐','DashboardView / ECharts','P1'),
('工作流节点点击','展开阶段说明、连接对应模块','workflow-nodes','P2'),
('读取记录','骨架之后由左向右显示真实波形','ECGSignal / API','P0'),
('鼠标查看波形','十字线、时间、电压、专家标签 Tooltip','ECharts axisPointer','P0'),
('点击真实标注','选中区域、参考线、单次光环、详情和局部波形切换','ECGSignal / BeatDetail','P0'),
('查看心拍细节/返回','展开真实单拍窗；不拉伸静态图片','beat-focus','P0'),
('滚轮/框选/拖拽/重置','视图缩放、标注坐标一致、手动操作暂停回放','dataZoom','P0'),
('心拍类别筛选','对应标注强调，其它类别淡化，计数同步','classFocus','P1'),
('真实推理','请求期间 Loading，响应后概率呈现，失败有提示','API + request cancellation','P0'),
('选择模型','保留同一心拍，当前卡片强调，其它模型可见','ModelResults / modelId','P0'),
('三模型比较','真实响应后呈现三个结果及精确表格','ModelResults','P0'),
('点击类别概率','三个模型同类别同步强调和差异说明','ProbabilityBar / focus','P0'),
('播放/暂停/继续','RAF 驱动、独立 Canvas 游标、滑动真实窗口','PlaybackClock','P0'),
('倍速/seek/重启','0.5/1/2/4 倍，基于实际时间锚点，无累计帧误差','PlaybackClock','P0'),
('经过真实标注','当前详情、真实缓存预测、计数与历史轨迹同步','playbackSegment','P0'),
('暂停后缩放','保持当前心拍与时钟，手动查看不被自动跟随抢回','onUserZoom','P0'),
('混淆矩阵悬停/点击','行列强调；打开真实保存样本与 ECG 入口','Research / ErrorCases','P1'),
('错误方向点击','按模型、真实类别和预测类别取已有样本','research/errors','P1'),
('患者热力图点击','显示真实支持量；仅 test 受试者显示已有 test 指标','Generalization Drawer','P1'),
('权重策略切换','Validation Macro-F1、Accuracy、类别 Precision/Recall、预测分布更新','weight_classes / weights CSV','P1'),
('图库筛选/搜索','保留条件、卡片重排与进入、每页 12 张缩略图','Gallery / MotionCard','P1'),
('图库大图/键盘/缩放','左右键、上一张下一张、缩放、说明折叠、返回实验','Ant Modal / local selection','P1'),
('答辩上/下一步','八步手动引导、重点说明柔和切换、真实模型调用','PresentationDemo','P1'),
('暂停答辩/全屏/退出','阻止下一步并暂停时钟，继续后恢复；浏览器全屏','demoPaused','P0'),
('减少动画/系统偏好','保持可读性和功能，关闭非必要动效','AnimationProvider','P0'),
]
matrix=['# 第四阶段交互矩阵','', '| 用户操作 | 实际状态变化 | 实现 | 优先级 |','| --- | --- | --- | --- |']
matrix += [f'| {a} | {b} | {c} | {d} |' for a,b,c,d in rows]
matrix += ['', '## 验证证据','', f'- 后端：{summary("phase4_backend.log")}。',f'- 开发 E2E：{summary("phase4_e2e_final.log")}。',f'- 独立生产 E2E：{summary("phase4_production_e2e.log")}。',
 '正常流程使用真实 API；延迟和故障注入仅用于验证加载、超时、缺图和重试，不作为医学数据。',
 '', '## 范围边界','',
 'LR/RF 没有逐 Epoch 损失日志，所以训练曲线明确展示已保存 CNN 日志；不伪造其他模型曲线。错误列表只展示原 test 保存预测，最多 20 条；新跳转后的实际推理单独执行。患者在 train/val 分区时不会生成不存在的 test 指标。']
write('phase4_interaction_matrix.md','\n'.join(matrix))

perf=data('phase4_playback_performance.json');dev=data('phase4_performance_dev.json');prod=data('phase4_performance_production.json')
performance=['# 第四阶段性能测量','', '环境：本机 Chrome / CPU。开发为 Umi Max，生产为 Umi 构建与同源 FastAPI。数据来自测试输出 JSON，不使用参考图数字。','',
 '| 指标 | 实际结果 |','| --- | --- |']
for label,key,unit in [('回放观察时长','duration_seconds','s'),('RAF 样本数','raf_samples',''),('浏览器帧回调平均频率','average_fps','FPS'),('帧间隔中位数','median_frame_ms','ms'),('帧间隔 P95','p95_frame_ms','ms'),('载入后重复推理/片段请求','repeated_inference_requests','次')]:
    v=perf.get(key);performance.append(f'| {label} | {f"{v:.2f} {unit}" if isinstance(v,(int,float)) else "尚未取得"} |')
if perf:performance += ['',f'显式 GC 后 JS heap：{perf["heap_before"]/1048576:.2f} → {perf["heap_after"]/1048576:.2f} MiB。该差异包含片段、波形、模型结果及界面对象的一次加载，不应直接解释为泄漏。']
performance += ['', '## API 往返耗时（每类 5 次）','', '| 环境 | ECG 窗口 ms | 单拍 CNN ms | 同拍三模型 ms |','| --- | ---: | ---: | ---: |']
for name,record in [('开发',dev),('生产',prod)]:
    vals=[record.get('api',{}).get(k,{}).get('mean_ms') for k in ['window','single','compare']]
    performance.append('| '+name+' | '+' | '.join(f'{v:.2f}' if v is not None else '尚未取得' for v in vals)+' |')
performance += ['', '## 优化与解释','',
 '- RAF 以 performance.now 的真实差值推进记录时间；seek 重设时间锚点；隐藏页面和组件卸载有清理。',
 '- 每帧只通知独立 Canvas 游标，语义 UI 约 10Hz，单拍内容按真实标注切换；不会 60Hz 重新生成整条 ECharts 数据。',
 '- 回放从一次真实片段批量推理中复用结果；逐拍详情读取仍是独立 API，报告不将它们藏掉或当作重复模型请求。',
 '- ECG 数据上限保持 30 秒与原后端限制；模型与信号沿用既有有界缓存。保存预测缓存最多 2 份，缩略图缓存最多 24 份。',
 '- 缩略图最大 640×440，保持比例，按需加载；原科研图像未改写，大图/下载仍为原文件。',
 '- 图表容器使用 ResizeObserver；清理实例、监听、RAF 与请求，保留减少动画模式。',
 '', '## 测量边界','',
 'FPS 是浏览器 RAF 间隔测量，不是逐像素 GPU 合成保证；不能据此声称所有机器恒定 60 FPS。当前是短时回放与有限导航循环，未完成小时级稳定性与多用户负载测试，不声称长期无泄漏。页面“就绪时间”包含等待语义内容和 networkidle，不等同于 LCP。',
 '', '原始产物：phase4_playback_performance.json、phase4_performance_dev.json、phase4_performance_production.json。']
write('phase4_performance.md','\n'.join(performance))

images=sorted(p.name for p in (DOCS/'screenshots/phase4').glob('*.png') if not p.name.startswith(('smoke_','probe_','contact_')))
review=['# 第四阶段视觉审查','',
 '参考：用户提供的三张浅色医学科技风页面。使用真实 React、ECharts 和本机接口实现；参考图不是背景，不用其示例数值。',
 '', '## 发现并修复','',
 '1. 原深蓝顶栏与横向导航改为白色顶栏、浅蓝可收起侧栏，内容保留真实数据来源。',
 '2. 旧页面局部样式覆盖新主题：用平台作用域规范优先级，统一类别颜色与背景。',
 '3. LESS 对最后一个自定义属性缺少分号报错：补齐分号，实际编译与构建后再运行。',
 '4. 初次 Motion 依赖预构建与记录扫描较慢：等待真实标题和 API，不截打包页或骨架。',
 '5. 完整截图时滚动位置导致固定导航出现在图中部：截图前回到页面顶端。',
 '6. 模型卡片过渡未结束就截图：等待请求和动效稳定；保持按模型对齐。',
 '7. 人工估算 ECG 像素坐标不可靠：测试改用 ECharts 实际绘图坐标，并验证返回的样本位置与时间。',
 '8. 原图库直接加载科研大图：增加保持比例的缓存缩略图，展示与下载原图分开。',
 '9. 系统减少动画在运行时切换未同步：改为原生 matchMedia 订阅，同时关闭 Ant Design 非必要过渡；已验证三级强度、系统覆盖及图库键盘操作。',
 '10. 波形轴提示可能落到邻近采样点：使用实际标注像素近邻命中并指定散点 seriesIndex。生产测试等待图表布局稳定后原生悬浮/点击，确认样本 487 与 1.353 s，且不触发不适用的自动推理。',
 '', '## 审查项目','',
 '1366×768、1440×900、1920×1080：动画结束布局、中文可读性、卡片高度、波形面积、表格局部横向滚动、body 横向溢出、未捕获异常和失败资源。1366/1440 主要详情可通过抽屉访问，1920 使用右侧实时详情。',
 '', '## 真实截图索引','']
review += [f'- [{name}](screenshots/phase4/{name})' for name in images]
review += ['', '回归截图另存 screenshots/phase4/regression；没有覆盖第三阶段截图和实验结果。人工审查结合全图、局部图及 contact_*.png 拼图。','',
 '## 保留边界','', '长研究页需要纵向滚动；小屏不强塞三列。科研原图沿用原配色与原文。动画减少设置仍保留功能性时间推进。没有生成不存在的 CNN/RF/LR 曲线或患者指标。']
write('phase4_visual_review.md','\n'.join(review))

backend=summary('phase4_backend.log');e2e=summary('phase4_e2e_final.log');production=summary('phase4_production_e2e.log')
write('phase4_final_report.md',f'''# ECG-AI 第四阶段交付报告

执行日期：2026-11-03。

## 交付范围

保留 React / TypeScript / Umi Max / Ant Design / ECharts 及真实 FastAPI 推理接口。重新设计项目总览、ECG 工作台、独立 AI 检测入口、实验中心、泛化分析、图库与答辩模式。浅色顶栏与可收起侧栏、N/S/V/F 统一颜色、全局动画强度和系统减少动画偏好已接入。

核心链路：真实标注点击 → 波形区域高亮 → 单拍详情 → 实际模型请求 → 三模型结果 → 跨模型概率类别联动 → RAF 历史回放同步。演示图像未替代真实图表，原始信号和模型概率不因动画改变。

新增组件与机制见 [动画设计](phase4_animation_design.md)，具体交互见 [交互矩阵](phase4_interaction_matrix.md)。

## 实际验证

| 检查 | 证据 |
| --- | --- |
| TypeScript | phase4_typecheck.log：{'通过' if 'tsc --noEmit' in read('phase4_typecheck.log') and 'error TS' not in read('phase4_typecheck.log') else '待最终核验'} |
| Umi 生产构建 | phase4_build.log：{'通过' if 'Build index.html' in read('phase4_build.log') and 'fatal -' not in read('phase4_build.log') else '待最终核验'} |
| 后端核心与只读扩展 | phase4_backend.log：{backend} |
| 完整开发浏览器回归 | phase4_e2e_final.log：{e2e} |
| 独立生产 / 无外网 | phase4_production_e2e.log：{production} |

截图与修复记录见 [视觉审查](phase4_visual_review.md)，真实测量与边界见 [性能报告](phase4_performance.md)。测试失败/调试记录保留为 iteration 或 smoke 文件，不能将它们当作最终通过证据。

## 新增的只读后端能力

`/api/research/errors` 读取保存的 test 预测，支持任务、模型、真实类别、预测类别和受试者；与已有混淆矩阵计数核对。研究摘要增加已有权重类别详情与患者 test 结果。图库提供按需、有限缓存的缩略图。没有重写后端模型、训练模型或修改正式实验结果。

## 已知限制

- 训练曲线只有已保存 CNN Epoch 日志，LR/RF 不补造曲线。
- 历史 test 已查看；四分类少数类及患者集中度仍限制泛化解释，模型一致不等于诊断准确。
- 目前为短时帧率与内存观察；未完成小时级和并发压力测试。
- 第三阶段已记录的 npm 残余风险仍存在；安装 Motion 后 npm 仍报告 71 项（10 low、44 moderate、16 high、1 critical），没有强制升级框架或宣称零风险。

## 本机运行

生产构建由 `web.backend.production:app` 在本机 8002 提供。当前交付已重新启动服务；刷新浏览器即可查看，首页 `/dashboard`，AI 检测 `/ai-inference`，答辩 `/presentation-demo`。
''')
print('Generated five phase4 documents from available evidence.')
