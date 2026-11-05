from pathlib import Path
import json,re
from PIL import Image,ImageDraw,ImageFont

web=Path(__file__).parent; docs=web/'docs/visual_fidelity'; refs=web/'design/reference/references'
def read(p):
 p=Path(p);return p.read_text(encoding='utf-8-sig',errors='replace') if p.exists() else ''
def result(name):
 matches=re.findall(r'^\s*(\d+ (?:passed|failed|skipped)(?: \([^\r\n]+\))?)',read(docs/name),re.M);return ' / '.join(matches) or '等待最终结果'
def write(name,text):(docs/name).write_text(text.strip()+'\n',encoding='utf-8')
def data(name):
 p=web/'docs'/name;return json.loads(read(p)) if p.exists() else {}

pairs=[('dashboard','01_dashboard_target.png','项目总览'),('ecg','02_ecg_workspace_target.png','ECG 工作台'),('comparison','03_ecg_analysis_target.png','同拍三模型比较'),('ai','04_model_comparison_target.png','AI 智能检测')]
output=docs/'comparisons';output.mkdir(exist_ok=True)
font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
for page,reference,title in pairs:
 paths=[refs/reference,docs/'before'/f'{page}_1672x941.png',docs/'after'/f'{page}_1672x941.png']
 if not all(p.exists() for p in paths):continue
 canvas=Image.new('RGB',(2532,520),'#e9f1fa');draw=ImageDraw.Draw(canvas)
 for i,(p,label) in enumerate(zip(paths,['参考设计（示意数据）','修改前（真实系统）','修改后（真实系统）'])):
  im=Image.open(p).convert('RGB');im.thumbnail((836,471));canvas.paste(im,(i*844,40));draw.text((i*844+10,8),label,font=font,fill='#182b49')
 canvas.save(output/f'{page}.png')

gap=read(docs/'gap_analysis.md')
gap+='''

## 实际修正与视觉循环

1. before：五尺寸 × 五页面，各保留视口截图和完整页面截图。1672 首次 AI 比较定位超时，before_retry.log 补拍通过。
2. iteration1：已实际查看 1672 图片。发现标题被旧 flex 对齐推到右侧、指标面板过高、回放按钮样式隐藏、主卡片高度影响首屏。
3. iteration2：修正标题左对齐、紧凑指标表、控制台间距、独立回放按钮及三卡标题位置。
4. after：单拍 SVG 改为响应式 ECharts；原始与滤波值保持不变；AI 父级缩略窗仅隐藏坐标轴，读取同一真实窗口。
5. 窄屏：64px 图标栏 + 原生菜单语义、Tooltip、可展开完整名称。745 取消三列强压，控制台改为双列表单，主波形置于其下方。
6. 加载图标残留：核对安装的 Ant Design 按钮实现，比较按钮补充稳定的 API 图标与 aria-label；真实加载仍由请求控制。五尺寸与生产测试重新通过。
7. 回放性能测试使用原固定 200px Seek 坐标，新横栏宽度下跳到了片段末尾。改为滑轨实际宽度的 20%，验证 seek 后继续前进、暂停静止和真实片段自然结束，不改变回放逻辑。

## GeneScope 核验

前端 src 与后端源码检索未发现 GeneScope；实际浏览器 DOM 与新截图未出现该浮层。不能由此判断具体是哪一个系统或浏览器组件，未删除其他应用功能。
'''
write('design_gap_analysis.md',gap)
write('implementation_report.md','''# 第五阶段代码实现

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
''')
checks=[('数量/百分比/对数','实际图表截图发生变化，比例轴和 log10 提示正确'),('类别联动','筛选 F 后中心数量和分区提示同步'),('真实标注','专家标注 sample 与详情/API annotation_sample 一致'),('三模型','API 返回三个不同 model_id，固定同一真实样本；概率来自各自返回值'),('模型切换','Random Forest 高亮改变，原样本位置保持'),('概率联动','同一类别在三个卡片同步强调'),('前后心拍','相邻真实标注位置切换；返回原样本'),('历史回放','RAF 游标推进；暂停后 data-time 保持；seek 后继续；0.5/1/2/4 倍'),('减少动画','系统 reduce 覆盖用户模式，波形 animation-name 为 none，功能仍可用'),('图库/实验/答辩','沿用完整回归：键盘与缩放、真实错误案例、八步演示和失败恢复'),('窄屏菜单','745px Tooltip 可读，展开完整菜单名，导航后折叠'),('溢出/异常','五尺寸浏览器截图与 body 宽度检查、pageerror 检查')]
write('interaction_checklist.md','# 第五阶段交互验收\n\n| 项目 | 验证方式 |\n| --- | --- |\n'+'\n'.join(f'| {a} | {b} |' for a,b in checks)+f'\n\n完整回归：{result("e2e_final.log")}。独立生产：{result("production.log")}。五尺寸截图：{result("after.log")}。\n\n真实三模型返回保存在 interaction/verified.json；故障注入仅用于测试请求失败、延迟和缺图，不充当医学数据。')
comparison=['# 设计稿与真实实现对照','', '对比图从左到右：参考稿、修改前、修改后。参考稿仅用于布局；截图和原始图片均保留，没有用图片替代网页。真实数据、字体和波形使逐像素误差不适合作为唯一评分。','']
for page,reference,title in pairs:
 comparison += [f'## {title}','',f'- 参考：../../design/reference/references/{reference}',f'- 修改前：[原图](before/{page}_1672x941.png)',f'- 修改后：[原图](after/{page}_1672x941.png)',f'- [并排对照](comparisons/{page}.png)','']
comparison += ['## 已还原与保留差异','', '| 页面 | 布局/交互/动画 | 仍有差异 |','| --- | --- | --- |',
'| Dashboard | 四 KPI、左类别/数量、中分区/概览、右双任务指标、横向流程；筛选和坐标模式均有真实状态更新 | 原图蓝色/玫红比例取决于真实数据；宏平均指标和工件数口径不同；插图是轻量 SVG，非原稿 3D 素材 |',
'| ECG | 控制/大波形/详情三列；独立回放和三模型；点击、模型切换、概率过渡、暂停/seek | 波形来自记录 200 的实际窗口，幅值与参考不同；保留原始/滤波双曲线；小桌面详情放在主图下并可用 Drawer |',
'| AI | 控制/单拍/推理结果三列、父级真实窗、下方三卡和回放 | 一致性说明在卡片下方；未增加参考图的第四个圆环卡；真实窗口设置保留在可展开项；1672×941 下回放栏需要略向下滚动，整体高度仍比参考稿长 |',
'| 实验 | 保留真实指标、混淆矩阵与错误样本，统一新框架 | 参考包没有对应实验页面设计，按全站 tokens 适配，不声称逐图还原 |','',
'小屏（745×671）采用纵向操作流程，不缩小整个桌面网页。截图同时保留 full 后缀完整页面；较长科研页面需要纵向滚动。','', '## 五尺寸证据','']
for w,h in [(1672,941),(1920,1080),(1440,900),(1366,768),(745,671)]:
 comparison += [f'- {w}×{h}：'+ ' · '.join(f'[{title}](after/{page}_{w}x{h}.png)' for page,_,title in pairs)+f' · [实验](after/experiments_{w}x{h}.png)']
write('visual_comparison.md','\n'.join(comparison))
perf=data('phase5_playback_performance.json');prod=data('phase5_performance_production.json')
perftext='短时实测原始记录尚未生成。'
if perf:perftext=f'回放观察 {perf["duration_seconds"]:.2f}s，RAF 回调平均 {perf["average_fps"]:.2f}/s，间隔 P95 {perf["p95_frame_ms"]:.2f}ms；载入后重复推理请求 {perf["repeated_inference_requests"]}。显式 GC 后 heap {perf["heap_before"]/1048576:.2f}→{perf["heap_after"]/1048576:.2f}MiB。不是长期无泄漏或 GPU 恒定帧率保证。'
write('final_report.md',f'''# ECG-AI 第五阶段交付

执行日期：2026-11-04。四张目标设计已逐张查看，完成实际 React 重构、五尺寸截图、设计对照与交互验证。主要页面和具体差异见 [视觉对照](visual_comparison.md)。

## 验证

| 检查 | 结果与证据 |
| --- | --- |
| TypeScript | {'通过' if 'tsc --noEmit' in read(docs/'typecheck.log') and 'error TS' not in read(docs/'typecheck.log') else '待核验'} · typecheck.log |
| 生产构建 | {'通过' if 'Build index.html' in read(docs/'build.log') else '待核验'} · build.log |
| 后端核心 | {result('backend_final.log')} |
| 全站交互回归 | {result('e2e_final.log')} |
| 独立生产/无外网 | {result('production.log')} |
| 五尺寸视觉与溢出 | {result('after.log')} |

{perftext}

原始性能：../phase5_playback_performance.json、../phase5_performance_dev.json、../phase5_performance_production.json。失败调试日志保留，最终结果以本表指定文件为准。

## 文档与截图

- [设计差异与修复过程](design_gap_analysis.md)
- [代码实现](implementation_report.md)
- [真实交互验收](interaction_checklist.md)
- [设计稿/修改前/修改后对照](visual_comparison.md)
- before / iteration1 / iteration2 / after 保留真实浏览器截图；comparisons 为并排拼图。

## 边界

真实模型、WFDB 与正式实验产物保持只读。参考中的数字和波形没有复制到推理数据。网页不声称像素完全一致；3D 心脏插图采用轻量 SVG，AI 一致性说明的位置和小屏详情布局有适配差异。依赖未新增，上一阶段已记录的 npm 残余风险仍保留；本轮未强制升级框架。

GeneScope：源码与浏览器 DOM 未检出，实际新截图不包含该浮层，不能判断其他软件的具体来源。

本机入口：[Dashboard](http://127.0.0.1:8002/dashboard)、[ECG](http://127.0.0.1:8002/ai-detection)、[AI 检测](http://127.0.0.1:8002/ai-inference)。刷新即可加载最新生产构建。
''')
print('Generated phase5 reports and reference/before/after comparisons.')
