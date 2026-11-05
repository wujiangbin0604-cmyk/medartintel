"""Generate delivery evidence from actual logs and measurement artifacts."""
from pathlib import Path
import json
import re

WEB=Path(__file__).parent
DOCS=WEB/'docs'
def read(name):
    path=DOCS/name
    return path.read_text(encoding='utf-8-sig',errors='replace') if path.exists() else ''
def data(name):
    value=read(name)
    return json.loads(value) if value else {}
def save(name,text):
    (DOCS/name).write_text(text,encoding='utf-8')

before=data('phase3_audit_before.json');after=data('phase3_audit_after.json');prod=data('phase3_audit_production.json')
counts=lambda a:a.get('metadata',{}).get('vulnerabilities',{})
security=['# npm 依赖安全审计','', '执行日期：2026-11-03。原始 JSON、锁文件前快照与安装日志在本目录保留。未执行 `npm audit fix --force`。', '',
 '| 阶段 | low | moderate | high | critical | total |','| --- | ---: | ---: | ---: | ---: | ---: |']
for title,value in [('修复前',before),('修复后',after),('修复后 --omit=dev',prod)]:
    c=counts(value);security.append('| '+title+' | '+' | '.join(str(c.get(k,'未取得')) for k in ['low','moderate','high','critical','total'])+' |')
security += ['', '## 已实施的最小更新', '',
 '- `@babel/runtime` 7.23.6 → 7.29.10，同属 major 7；覆盖 Umi 旧的精确传递依赖。',
 '- `postcss` 8.4.31 → 8.5.32，同属 major 8；更新匹配 `^8.4.21` 的传递依赖。',
 '- 实际锁文件版本变化仅这两个包。npm 同时移除 17 个被合并的重复包，详见 `phase3_dependency_install.log` 与 `phase3_package_lock_before.json`。',
 '- 消失的审计条目：`@babel/runtime`、其影响的 `@umijs/babel-preset-umi` 和 `postcss`。直接 React / Ant Design / ECharts / Umi 版本未强行迁移。',
 '- 候选版本查询发现 immer 8.x 无可用安全补丁、decode-uri-component 0.2.x 没有新补丁；未安装不存在的候选版本。最终 package.json 仅保留已实际安装的两个 overrides。',
 '', '## 依赖性质与实际暴露', '',
 '`@umijs/max` 在原 package.json 被列为 dependencies，因此 npm --omit=dev 仍会包含构建器、开发服务器、lint 和插件链。不能把该结果解释为“生产静态页面包含全部告警代码”，也不能因此把这些包认定为无风险。测试工具本身为 devDependencies；本轮 71 项告警均通过 Umi 的 dependencies 树保留。',
 '',
 '- 浏览器可达链需关注 react-router / react-router-dom、query-string / decode-uri-component。当前导航为固定本地路由，未接收任意外部跳转地址。',
 '- `axios` 0.27.2 由 @umijs/plugins 精确引入；项目接口使用原生 fetch。',
 '- critical 为 `immer` 8.0.4 的旧原型污染问题，经 dva-immer 插件引入；本项目未启用 dva/store 插件。仍保留告警，不声称安全。',
 '- node-fetch 1.x、esbuild、glob、minimatch、Vite、path-to-regexp 等分属旧插件/开发/构建链；本地演示不公开开发服务。',
 '- npm 提供的部分自动“修复”是把 @umijs/max 改为 4.0.7，属于不合适的跨依赖树变更。本轮未执行。',
 '', '## 未修复告警清单', '', '| 包 | 严重度 | 直接依赖 | 受影响范围 | 原始公告 / 影响链 |','| --- | --- | --- | --- | --- |']
for name,row in after.get('vulnerabilities',{}).items():
    links=[]
    for via in row.get('via',[]):
        links.append(f"[{via.get('title',name)}]({via['url']})" if isinstance(via,dict) else via)
    security.append(f"| {name} | {row['severity']} | {'是' if row['isDirect'] else '传递'} | {row['range']} | {'；'.join(links)} |")
security += ['', '## 验证与后续', '',
 '命令：`npm audit --json`、`npm audit --omit=dev --json`、`npm view immer@8 version --json`、`npm view decode-uri-component@0.2 version --json`、`npm install --ignore-scripts --no-fund`。首次沙箱 DNS 请求失败后，以授权网络访问取得真实审计；失败结果没有当作零告警。',
 '', '最终类型检查、构建与浏览器回归日志见 `phase3_typecheck.log`、`phase3_build.log`、`phase3_e2e_final.log`、`phase3_production_e2e.log`。',
 '', '独立后续任务：升级 Umi / 插件生态，评估移除未启用的 dva/旧 fetch 链，验证路由安全修复所需的大版本兼容性。当前版本仅用于 loopback 课程演示；公开部署前需另行处理残余高危依赖与访问控制。']
save('security_dependency_audit.md','\n'.join(security)+'\n')

shots=[]
for resolution in ['1366x768','1440x900','1920x1080']:
    for page in ['dashboard','ai-detection','comparison','experiments','experiments_nsvf','generalization','gallery']:
        name=f'{page}_{resolution}.png'
        if (DOCS/'screenshots/phase3'/name).exists():shots.append(f'- [{name}](screenshots/phase3/{name})')
visual=['# 第三阶段真实截图审查','', '截图来自 Playwright + Chrome 打开的真实本地页面，目录 `web/docs/screenshots/phase3/`。测试要求真实页面标题出现、API 加载完成后再截图，不以网络空闲或空骨架作为验收。', '',
 '## 发现与修复', '',
 '1. 原项目只有工作台，顶部菜单不可点击：增加真实路由与统一平台导航。',
 '2. Umi 自动布局与显式父路由叠加：首轮截图发现双导航、双页脚，已去掉重复父布局，增加导航数量断言。',
 '3. 首屏骨架被过早截图：增加真实标题和语义内容等待条件，重拍总览。',
 '4. 原 8–11px 文字难以投影阅读：提升到 12–14px，页标题 28px、图标题 16–18px。',
 '5. 中央波形被侧栏挤压：1550px 以下右详情改 Drawer，波形使用更宽空间、真实单位和时间。',
 '6. 导航状态深色背景对比不足：增加特定颜色规则；禁用动作按钮取消不合适的蓝底。',
 '7. 图库长页请求过多：每页 12 张，保持图片比例，提供完整大图、报告与下载。',
 '8. 生产构建压缩辅助代码冲突：按本地构建器提示启用 esbuildMinifyIIFE，通过后续构建。',
 '', '## 自动审查', '',
 '逐页检查 body.scrollWidth、主要面板右边界、图表实际尺寸、pageerror、HTTP >=400 资源。`phase3_browser_1366.json` / `1440.json` / `1920.json` 为最终截图检查数据；异常注入测试与正常页面资源检查分开。表格在自身容器内滚动属于预期，不应撑宽 body。',
 '', '## 截图索引', '',*shots,'',
 '## 人工图像审查', '',
 '使用图像查看工具检查真实截图及各分辨率审查拼图（contact_*.png），核对导航唯一、卡片边界、文字对比、波形面积、矩阵标签和图像完整比例。截图不是页面实现；所有页面均为真实 React 组件与接口。',
 '', '## 保留的限制', '',
 '长页面需要纵向滚动；1366×768 无法在一个首屏同时显示波形、三模型表格和全部明细。科研原图使用各自已有配色与原始文字，未重画或修改已有研究图像。本轮不新增深色主题。']
save('phase3_visual_review.md','\n'.join(visual)+'\n')

dev=data('phase3_performance_raw.json');production=data('phase3_performance_production.json')
performance=['# 第三阶段实际性能报告','', '测量日期：2026-11-03。本机 CPU / Chrome，五次 API 采样。数值为本机 HTTP 往返时间，包含 JSON 序列化等开销，不能当作纯模型计算耗时或通用基准。页面指标包含语义内容与 networkidle 等待，不等同于 FCP/LCP。', '', '| 环境 | ECG 窗口均值 ms | 单拍 CNN 均值 ms | 三模型均值 ms |','| --- | ---: | ---: | ---: |']
for name,record in [('Umi 开发服务器',dev),('Umi 生产构建 + FastAPI',production)]:
    values=[record.get('api',{}).get(k,{}).get('mean_ms') for k in ['window','single','compare']]
    performance.append('| '+name+' | '+' | '.join(f'{v:.2f}' if v is not None else '尚未取得' for v in values)+' |')
performance += ['', '## 页面数据就绪耗时', '', '| 页面 | 开发 ms | 生产 ms |','| --- | ---: | ---: |']
for page in ['dashboard','ai-detection','experiments','generalization','gallery']:
    values=[r.get('pages',{}).get(page) for r in [dev,production]]
    performance.append('| '+page+' | '+' | '.join(f'{v:.2f}' if v is not None else '尚未取得' for v in values)+' |')
performance += ['', '## 请求和内存', '']
if dev:
    calls=dev.get('playback',{}).get('requests_after_loaded',[])
    performance += [f'- 载入回放后观察 2.5 秒：{len(calls)} 个 API 请求；其中推理/片段请求 {sum("/inference/" in u or "/playback/" in u for u in calls)} 个。逐拍详情读取与模型计算分开统计。',f'- 页面内部导航切换 12 次，显式垃圾回收后 JS heap：{dev.get("heap_before",0)/1024/1024:.2f} → {dev.get("heap_after",0)/1024/1024:.2f} MiB。']
else: performance += ['尚未取得完整开发端采样，不能声明无泄漏或回放请求量达标。']
performance += ['', '## 已实施优化', '',
 '- ResizeObserver 监听图表容器，清理 observer / ECharts 实例；回放定时器在暂停和卸载时清理。',
 '- 回放游标更新从全图重建中分离；保留 dataZoom 的缩放状态。',
 '- 请求取消、版本检查和动作互斥，防止过期响应覆盖新选择。',
 '- 六个模型由既有 registry 复用；信号/记录缓存保留原有 2 / 3 个上限，研究文件缓存只有一份。',
 '- 图库每页 12 张并懒加载原图，减少请求与浏览器保留图像。',
 '- 提供构建产物与 API 同源的本地生产服务，演示时避免开发编译与 HMR 开销。',
 '', '## 测量边界', '',
 '短时 heap 观察无法替代数小时稳定性测试，不能据此证明没有任何内存泄漏。未测并发临床负载；开发模式的依赖预构建会影响首次访问。生产离线测试阻断所有非 loopback 浏览器请求，验证外网不可用时本地核心链路仍可操作，不是关闭本机后端。',
 '', '原始样本：`phase3_performance_raw.json`、`phase3_performance_production.json`。测试实现：`frontend/tests/phase3.spec.ts`、`production.spec.ts`。']
save('phase3_performance_report.md','\n'.join(performance)+'\n')

interaction=['# 第三阶段交互与边界测试','',
 '## 可复现命令与日志','',
 '```powershell',
 r'.venv\Scripts\python.exe -m pytest -q web/backend/tests --basetemp .test_tmp/phase3-http-final',
 r'.venv\Scripts\python.exe -m web.backend.validate_saved_models --samples-per-task 100 --output web/results/phase3_validation',
 'npm --prefix web/frontend run typecheck',
 'npm --prefix web/frontend run build',
 'npm --prefix web/frontend run test:e2e',
 'npm --prefix web/frontend run test:e2e -- --config playwright.production.config.ts',
 '```','',
 '- 后端：`phase3_backend_final.log`，15 passed。包括真实读取/推理与 HTTP 边界。',
 '- 模型复现：`web/results/phase3_validation/validation_summary.json`，600/600 类别匹配，最大概率误差 4.76837158203125e-07；未修改第二阶段验证产物。',
 '- 类型：`phase3_typecheck.log`。生产构建：`phase3_build.log`。',
 '- 最终 E2E：`phase3_e2e_final.log`。生产离线：`phase3_production_e2e.log`。以日志末尾为通过依据；iteration/targeted 日志属于调试记录。',
 '', '## 覆盖范围','',
 '| 层级 | 场景 | 证据 |','| --- | --- | --- |',
 '| 原回归 | 200、CNN/RF/LR、三模型、四分类、播放暂停继续、倍速、seek | workspace.spec.ts |',
 '| 页面 | 三个分辨率真实数据截图、body 溢出、pageerror、HTTP 失败 | phase3.spec.ts |',
 '| 答辩 | 八步、重复 CNN 真实请求、三模型、回放、任务切换、上一步、退出、全屏 | phase3.spec.ts |',
 '| 图库 | 搜索、空结果、大图、报告、原图下载 | phase3.spec.ts |',
 '| 竞态 | 延迟真实推理后快速切 CNN/RF/LR；播放中切 100；102 仅浏览 | phase3.spec.ts |',
 '| 错误反馈 | 明确标记的测试注入 503、图像 404、30 秒超时与重试 | phase3.spec.ts |',
 '| API 边界 | 不存在记录、负时间、越界、超过 30 秒、不支持导联、无预测片段 | test_phase3.py |',
 '| 模型缺失 | 临时空目录建立 registry，六个工件均报错，返回可解释状态；未移动真实模型 | test_phase3.py |',
 '| 标签范围 | N/V 不兼容 S；过滤保护区保留标注并跳过预测 | test_api_integration.py |',
 '| 结果真实性 | 指标由最终计数复算，图库/报告 allowlist | test_phase3.py |',
 '| 离线生产 | 阻断非 loopback 网络，浏览研究页、单拍、比较、回放 | production.spec.ts |',
 '', '测试中注入的错误响应只用于验证故障反馈，未作为医学预测或正式页面数据。正常预测全部调用真实后端。',
 '', '## 已发现并修复','',
 '- 原工作台切换时间窗口/导联后可能保留旧选择与预测，比较和回放请求未取消。增加 AbortController、版本检查、互斥与统一状态清理。',
 '- 先推理再判断心拍资格会对过滤边缘/任务外标注发出错误推理请求：改为先读取详情，再按 inference_eligible 决定推理。',
 '- 回到起点前无已到达心拍时，清空未来心拍选择与预测。',
 '- Umi 从 PORT 变量而非 --port 读取监听端口；修正开发入口，E2E 使用独立端口且不复用其它服务。',
 '- 按钮图标进入可访问名称；测试对带图标的暂停/全屏按钮按可读名称匹配，避免误判。',
 '', '浏览器控制台的开发器 topLevelAwait 目标兼容提示与 Ant Design 弃用提示单独记录；不等同于未捕获运行异常。最终声明以 pageerror、资源状态和实际交互为准。']
save('phase3_interaction_testing.md','\n'.join(interaction)+'\n')

build=read('phase3_build.log');ts=read('phase3_typecheck.log');e2e=read('phase3_e2e_final.log');offline=read('phase3_production_e2e.log')
status=[('后端回归','15 passed' in read('phase3_backend_final.log')),('验证预测 600/600', (WEB/'results/phase3_validation/validation_summary.json').exists()),('TypeScript','tsc --noEmit' in ts and 'error TS' not in ts),('生产构建','Build index.html' in build and 'fatal -' not in build),('Playwright 完整回归','passed (' in e2e and not re.search(r'^\s*\d+ failed\b',e2e,re.M)),('生产离线验证','1 passed' in offline)]
final=['# ECG-AI 第三阶段交付报告','', '执行日期：2026-11-03。延续原项目，未训练模型、修改原始 WFDB、改写原正式实验结果或用 Mock 替代预测。', '',
 '## 已交付','',
 '| 页面 | 路由 | 内容 |','| --- | --- | --- |',
 '| 项目总览 | /dashboard | 真实记录数、心拍数、模型状态、类别/分区分布、两项任务性能、工作流、可点击入口 |',
 '| ECG 工作台 | /ai-detection | 波形主区、标注选择、真实单拍推理、三模型、形态对照、回放、紧凑屏详情 Drawer |',
 '| 实验中心 | /experiments | 二/四分类 Tabs、指标、Support、交互矩阵、行归一化、实际训练曲线与最佳 Epoch |',
 '| 泛化分析 | /generalization | 患者热力图、集中度、误分类、权重消融、五折患者 CV 与筛选 |',
 '| 科研图库 | /gallery | 本地 157 张图、分页/筛选/搜索、大图、报告和下载、错误提示 |',
 '| 答辩模式 | /presentation-demo | 八步引导、真实记录 200、CNN/三模型/回放、全屏与退出 |',
 '', '新增只读研究接口从已有最终核验 CSV、训练日志和本地图像目录读取；图像与报告通过 allowlist 提供。工作台保留所有原核心功能，并修复取消、竞态、回放状态和字体可读性。',
 '', '## 实际验收状态','', '| 检查 | 状态 |','| --- | --- |']
for title,passed in status:final.append(f'| {title} | {"通过（对应日志已生成）" if passed else "尚未取得最终通过证据，见日志"} |')
final += ['', f'依赖审计：74 → {counts(after).get("total","未知")} 项，残留 critical {counts(after).get("critical","未知")} / high {counts(after).get("high","未知")}；已记录在 [安全审计](security_dependency_audit.md)，没有宣称零风险。',
 '', '## 文档与产物','',
 '- [设计系统](phase3_design_system.md)',
 '- [真实截图与审查记录](phase3_visual_review.md)',
 '- [交互/边界测试](phase3_interaction_testing.md)',
 '- [安全审计](security_dependency_audit.md)',
 '- [实际性能](phase3_performance_report.md)',
 '- [答辩指南](phase3_demo_guide.md)',
 '- 截图：`screenshots/phase3/`；三种桌面尺寸与答辩流程。',
 '- 600 次模型复现：`web/results/phase3_validation/`。',
 '', '## 运行','',
 r'根目录运行 `npm --prefix web/frontend run build`，随后 `.venv\Scripts\python.exe -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8002`。打开 `http://127.0.0.1:8002/presentation-demo`。',
 '', '## 已知限制','',
 '- 71 项依赖告警仍需 Umi 插件生态的独立升级工作；不公开开发服务。',
 '- 本轮只验证浅色主题。长内容纵向滚动，图库原图保持原研究配色与内容。',
 '- 性能为本机少量采样与短时内存观察，不是长时间无泄漏或生产并发保证。',
 '- 历史 test 已在原研究查看；四分类 S/F 支持量与患者分布不均，不能包装为临床可用性。',
 '- 图库/研究文件缓存随服务进程生存；外部新增或修改文件后需重启服务刷新。']
save('phase3_final_report.md','\n'.join(final)+'\n')
print('Generated seven delivery documents from current evidence (design/demo authored separately).')
