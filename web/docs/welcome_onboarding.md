# ECG-AI 首次欢迎引导交付说明

日期：2026-11-04。已在现有 React / Umi Max / Ant Design / Motion 平台中实现，无新增 npm 依赖，未修改后端模型、训练流程或实验结果。

## 体验入口

- [平台首页](http://127.0.0.1:8138/dashboard)：首次进入自动显示欢迎弹窗。
- [平台根地址](http://127.0.0.1:8138/)：跳转 Dashboard 并支持首次欢迎。
- 已完成引导的用户，可在首页游戏推荐卡点击“查看欢迎引导”主动重开。
- 游戏路由仍为 `/interactive-lab/heartbeat-hunter`。

当前本地生产服务复用已有 `web.backend.production`，从 `web/frontend/dist` 读取最新构建。后续启动方式：

```powershell
# E:\医学人工智能
.\.venv\Scripts\python.exe -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8138
```

修改前端后在 `web/frontend` 运行 `npm run build`。不需要重新训练模型或生成游戏数据。

## 首次访问逻辑

欢迎组件挂在 MedicalLayout，独立于 Dashboard 数据请求和页面主体。仅 `/` 与 `/dashboard` 在首次访问时自动展示；直接访问科研页或游戏页不会强制插入欢迎弹窗。

用户可选择：

- **开始心跳挑战**：读取游戏 config 确认可用关卡数量，再记录完成状态并进入游戏准备页面。不调用 start，不创建计时会话。
- **先逛逛平台**：记录完成状态并关闭弹窗，保持当前页面，不请求任何游戏接口。
- 关闭按钮或 Escape：按关闭引导记录完成状态，不强制跳转。
- **下次不再自动显示**：保存明确的不再自动展示偏好；本版本不论是否勾选，完成后都只自动展示一次。弹窗底部直接说明该规则。

跳过会取消尚未完成的可用性检查，异步响应不会在用户离开弹窗后突然导航。开始按钮有请求互斥和加载状态；失败后保留当前页面，提示“游戏暂时不可用”，允许再次点击重试或浏览平台。

## localStorage 与版本策略

`ecg_ai_welcome_v1` 保存如下元信息：

```json
{
  "version": 1,
  "completed": true,
  "choice": "challenge",
  "doNotAutoShow": false,
  "completedAt": "ISO-8601 timestamp"
}
```

choice 为 challenge / browse / close。只存引导状态与时间，不保存心电数据、患者信息、专家标签或模型结果。

当前策略固定为 v1；刷新、普通发布与进入其他页面均不重置状态。未来若产品明确决定推出新版引导，应显式升级 key 和版本判断，并读取旧版 doNotAutoShow 尊重退出偏好；本次没有自动升级或定期重复展示逻辑。损坏或不符合 v1 结构的数据按未完成处理。

教程独立使用 `ecg_ai_hunter_tutorial_v1`，不与欢迎状态混用。读取/写入/删除均通过安全封装；Storage 被禁用或配额错误时退回当前标签页内存，页面和游戏仍可使用。动画设置和 Dashboard sessionStorage 写入也补上异常处理，避免存储异常导致平台崩溃。

存储不可用时不能保证刷新后的持久性；关闭前的同一标签页运行期间仍可记住状态。这是明确的降级行为。

## 欢迎视觉与动画

桌面采用双栏白色圆角卡片：左侧 Logo、欢迎标题、真实 ECG / 专家闯关 / AI 学习介绍和操作；右侧冰蓝渐变、轻量 SVG 心脏、手柄及 ECG 视觉预览。所有样式限于欢迎组件和新增推荐卡，不重写既有工作台。

视觉预览是明确标注的装饰 SVG：**“视觉演示 · 非真实推理结果”**，分数写作“得分示意 +100”。没有把它伪装为真实 ECG 片段、当前患者信号或模型推理结果。实际游戏仍只使用既有真实 MIT-BIH 服务。

动画包括遮罩淡入、卡片上移淡入、文案分段显现、SVG 波形一次绘制、一次选择脉冲及按钮 hover 柔光。所有按钮从出现时即可操作，不需要等待动画。Motion 和 CSS 同时遵循系统 prefers-reduced-motion 及平台减少动效设置；装饰动效没有无限循环。

Modal 保留 Ant Design 的焦点管理、Escape 关闭与键盘操作，并使用真实 Modal title 提供可访问名称；可视标题保留在自定义卡片内。窄屏分数和选中标记采用独立文字/圆形元素，避免随 SVG 横纵比例变化被拉伸。

## 游戏导航和首次教程

欢迎入口导航时带一次性 `?welcome=1`，游戏页消费后立即移除该参数，避免刷新时反复重置。欢迎跳转总是进入准备状态，不自动恢复旧局计时。

首次游戏访问弹出三步简短教程：观察真实 ECG → 选择 V 组心拍 → 提交并复盘。教程明确写明“阅读教程不会开始计时”；关闭教程后仍需主动点击“开始挑战”才发送 start。教程未关闭时，开始动作和按钮均被保护。

欢迎完成状态与教程完成状态分离。普通已知玩家刷新游戏仍可通过已有匿名会话恢复；首次欢迎的导航意图不会残留到后续刷新。真实游戏配置失败时，直接访问游戏页也有“重试连接”和“返回首页”，不会变成空白页面或可点击但无效的开始按钮。

## 持续游戏入口

- 左侧“心电互动实验室”与“Heartbeat Hunter · 心跳猎人”子入口，在展开侧栏时常驻，不再要求先进入实验室才显示子入口。
- Dashboard 新增浅蓝推荐卡，含游戏图标、小型装饰 ECG、难度标签、开始挑战和主动重开欢迎的按钮。
- 未追加占用顶部导航空间的快捷项，既有模型、数据集和动效设置保留。

## 从游戏过渡到真实分析

结算后新增“再来一次”“查看本轮答案”“看看 AI 如何判断”“探索 ECG 分析平台”。

- 再来一次：复用既有重新挑战逻辑。
- 查看本轮答案：定位到实际专家标签与逐拍学习解析，遵循 reduced motion。
- 看看 AI 如何判断：导航 **现有 AI 检测页 `/ai-inference`**，携带 `record_id`、`annotation_sample`、`task=nv`、实际时间和来源。
- 探索 ECG 分析平台：进入 `/ai-detection` 工作台，可携带同一心拍定位信息。

检测页兼容新增的明确参数名与已有 `record` / `sample` 链接。显式指定心拍时，先定位该专家 sample，再按原逻辑读取局部真实 ECG 并调用真实推理 API，避免默认选第一拍覆盖游戏指定心拍。游戏分数和答案不作为推理输出传入。

原来的游戏页内三模型对比保留，按钮改为“本页对比三个模型”，与用户要求的导航入口区分。模型本身及评分权威来源均未改动。

## 响应式与实际截图

实际浏览器检查了 1920×1080、1440×900、1366×768 和 745×900。桌面双栏，800 px 以下变为文案 → ECG 预览 → 操作按钮的单栏顺序。弹窗设置视口内最大高度和内部滚动；检查了边界、footer 可见、主要按钮可点击及 Dashboard 无横向溢出。

18 张真实截图均在 `web/docs/screenshots/welcome_onboarding/`：

- [1920 欢迎](screenshots/welcome_onboarding/welcome_1920x1080.png)
- [1440 欢迎](screenshots/welcome_onboarding/welcome_1440x900.png)
- [1366 欢迎](screenshots/welcome_onboarding/welcome_1366x768.png)
- [745 窄屏欢迎](screenshots/welcome_onboarding/welcome_745x900.png)
- [Hover 主按钮](screenshots/welcome_onboarding/hover_1440x900.png)
- [首页游戏推荐卡](screenshots/welcome_onboarding/dashboard_card_1440x900.png)
- [首次教程](screenshots/welcome_onboarding/first_game_tutorial.png)
- [游戏准备页面](screenshots/welcome_onboarding/game_ready.png)
- [结算后探索入口](screenshots/welcome_onboarding/postgame_ai_entry.png)
- [真实 AI 同拍推理页](screenshots/welcome_onboarding/real_ai_inference.png)
- [不可用状态](screenshots/welcome_onboarding/game_unavailable.png)
- [减少动效](screenshots/welcome_onboarding/reduced_motion.png)

欢迎、hover 和教程截图按实际视口保存，避免 full-page 截图把遮罩范围以外的滚动内容混入弹窗验收。游戏和科研页面按完整内容保存。

## 实际测试结果

| 检查 | 结果 |
|---|---|
| `npm run typecheck` | 通过 |
| `npm run build` | 通过，实际 Umi 生产构建 |
| 原 Heartbeat Hunter Playwright 回归 | 10 项通过 |
| 欢迎引导 Playwright | 11 项通过，58.7 s |
| 追加原平台交互回归 | 1 项通过，12.8 s（实际测试动作 4.1 s） |
| 合计浏览器场景 | 22 项全部验证通过，分别运行 |

覆盖首次根地址欢迎、进入真实游戏、跳过无游戏请求、完成/刷新/清除状态、checkbox、推荐卡、常驻子菜单、教程期间无 start、主动开局、刷新恢复、真实 AI 同拍推理、工作台跳转、不可用提示与恢复、Storage 安全降级、reduced motion、键盘关闭、四种视口、原有游戏全流程。

追加原平台回归实际操作 Dashboard 对数坐标与 V 类筛选、ECG 专家心拍点击，并调用真实推理；随后进入 AI 检测页，切换到 Random Forest，验证服务返回 `model_id=random_forest` 和界面显示。没有只检查按钮存在。

开发迭代中发现并修复：根地址首次入口判断、Ant Design 在 title 为空时不会生成 dialog 可访问名称、窄屏 SVG 文字/圆形变形、存储禁用时既有设置写入异常。修复后重新运行相关浏览器场景。

复现（工作目录 `web/frontend`，测试服务端口 8136）：

```powershell
npm run typecheck
npm run build
npx playwright test --config playwright.onboarding.config.ts
```

该配置包含 `welcome-onboarding.spec.ts`（12 项）和 `heartbeat-hunter.spec.ts`（10 项），使用独立测试数据库。真实 AI 断言检查实际推理响应中的 annotation_sample/task/model_id，未 mock 推理结果。仅不可用场景模拟 config 503，以验证降级界面。

## 已知边界

- 状态按浏览器和同源保存，不跨设备或账号同步；禁用存储时仅保证当前标签页运行正常。
- 不自动对未来版本重新弹窗；未来重新展示需要明确升级策略，并尊重已保存的不再自动展示偏好。
- 已验证上述桌面和 745 px 视口及键盘/reduced motion；未宣称完成所有移动浏览器或屏幕阅读器组合验收。
- 欢迎预览是装饰示意；真实信号仅在用户主动开始游戏后加载。游戏暂时不可用时首页可继续浏览。
- 保持本地课程平台的既有范围，没有增加云端账户、医学隐私存储或新的模型训练。

## 主要改动

- `src/components/onboarding/`：欢迎、预览、推荐卡、状态和样式。
- `src/utils/browserStorage.ts`：安全本地存储封装。
- `src/layouts/MedicalLayout.tsx`：挂载欢迎、常驻游戏子入口。
- `src/pages/dashboard/FidelityDashboard.tsx`：新增推荐卡。
- `src/pages/interactive-lab/HeartbeatHunter.tsx`：首次教程、准备页导航、结算探索入口、不可用处理。
- `src/pages/ai-detection/index.tsx`：精确心拍参数兼容与选择优先级。
- `src/utils/motion.tsx` / `src/hooks/useSessionState.ts`：存储异常降级。
- `tests/welcome-onboarding.spec.ts` / `playwright.onboarding.config.ts`：行为、真实模型、响应式验收。
