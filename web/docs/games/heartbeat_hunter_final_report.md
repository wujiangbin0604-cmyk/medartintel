# Heartbeat Hunter 交付报告

交付日期：2026-11-04。实现已写入现有 React/Umi/Ant Design ECG-AI 和 FastAPI 平台，已运行生产构建及真实浏览器测试。

## 体验地址与启动

本地体验：[Heartbeat Hunter](http://127.0.0.1:8138/interactive-lab/heartbeat-hunter)，入口页：[心电互动实验室](http://127.0.0.1:8138/interactive-lab)。服务仅监听本机回环地址，不发布到公网。

后续启动：在 `E:\医学人工智能` 执行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8138
```

首次或修改前端后先在 `web/frontend` 执行 `npm run build`。关卡索引已随代码生成；如原始数据有变化，重新执行 `python -m web.backend.build_heartbeat_levels` 并 `--check`。

本次启动进程记录在 `web/runtime/hunter_server.pid`，日志为同目录 `hunter_server.stdout.log`、`hunter_server.stderr.log`。请勿并行启动相同端口的重复服务。

## 已完成

- 互动实验室路由、左侧入口和游戏子入口；沿用既有浅蓝医学科技风。
- 完整三难度、每轮五关、非重复关卡、重玩、下一关、暂停/恢复规则、刷新恢复。
- 真实 MIT-BIH 原始 MLII 物理信号、医学网格、时间轴、真实 mV、记录与采样率信息。
- 新手全候选隐藏类别；标准/挑战不返回候选标签或位置。
- 波形坐标换算、明确容差、一对一确定性匹配、选择/取消/移除/清空。
- 服务端随机会话、权威截止时间、选择检查点、超时宽限与结算、重复提交幂等。
- 正确/误选/漏选、Precision、Recall、连击、时间奖励、可解释积分和等级。
- Motion、ECharts、CSS、rAF 动画：进入、波形绘制、扫描、滚动窗口、选择扩散、结果逐拍出现、连击、分数过渡；支持减少动态效果。
- 默认静音的原创合成音效、开关和音量。
- SQLite 匿名记录、每难度个人最佳、最近成绩和五关累计分数。
- 全部专家原始/AAMI 标签、逐拍局部波形、已有 LR/RF/CNN 对比、带记录与时间参数跳转工作台。
- 实际测试和 PNG 截图、规则/API/设计/数据校验/测试文档。

## 数据

62 个经校验的真实关卡：新手 21、标准 21、挑战 20。使用实际本地记录 100、105、106、108、109、114，360 Hz，MLII。来源：[PhysioNet MIT-BIH 1.0.0](https://physionet.org/content/mitdb/1.0.0/)。没有生成或手绘游戏 ECG。

索引包含原始文件 SHA-256 和真实专家 symbol/sample，保存在后端。所有窗口仅含可明确映射的 N/V 心拍，排除 S/F/Q、未知心拍、噪声/扑动标记及对应前置状态、滤波保护区和边界不完整心拍。原有训练模型、processed 数据和实验结果未修改。

## 验证结果

- TypeScript 检查通过。
- 前端生产构建通过。
- 后端 37 项 pytest 通过。
- Playwright 10 项生产浏览器场景通过，含十次页面往返稳定性检查。
- 62 个关卡文件哈希、波形、标注与安全区域校验通过。
- 1920×1080、1440×900、1366×768 下无横向溢出；原 ECG 工作台实际波形回归正常。
- 已保存 23 张真实截图，覆盖入口、准备、进行、选择、Combo、最后 10 秒、专家揭晓、最终成绩与教学解析。
- 3 s 挑战回放采样 537 帧，帧间隔 median 5.6 ms / P95 5.7 ms，>50 ms 为 0。游戏页面业务代码约 14.9 kB gzip；ECharts 等复用已有依赖，没有新增 npm 依赖。

详见 [测试记录](heartbeat_hunter_testing.md) 和 [机器可读性能采样](heartbeat_hunter_performance.json)。

## 截图

- [1920 新手进行与选择](../screenshots/heartbeat_hunter/selected_1920x1080.png)
- [1440 结算和学习解析](../screenshots/heartbeat_hunter/result_1440x900.png)
- [1366 结算和学习解析](../screenshots/heartbeat_hunter/result_1366x768.png)
- [真实连击反馈](../screenshots/heartbeat_hunter/combo.png)
- [挑战历史回放](../screenshots/heartbeat_hunter/challenge_replay.png)
- [最后 10 秒](../screenshots/heartbeat_hunter/last_10_seconds.png)
- [三模型教学对比](../screenshots/heartbeat_hunter/teaching.png)

## 实际边界

- 面向本地单人课程演示，使用单个 Uvicorn worker；没有云账号、可信身份、跨用户竞争榜或多进程事务协调。
- 答案不出现在未结束的游戏响应，但原教学平台和本机数据文件仍允许查阅专家标注，不宣称竞赛级反作弊隔离。
- 挑战模式为历史数据回放、批量提交，未实现逐拍实时判分；此选择避免作答中泄露部分答案。
- 动画结算以选择顺序累计 Combo，漏选单独扣分；不将游戏分数称为医学诊断能力。
- 内容多时正常纵向滚动；未为每种分辨率强制把全部学习解析塞入首屏。
- 已做短期帧采样和十次页面往返，未做数小时压力、多人并发、全部手机设备或人工听音验收。

## 主要文件

- `web/backend/heartbeat_hunter.py`：私有会话、时间、匹配、评分、历史和路由。
- `web/backend/build_heartbeat_levels.py`：真实数据关卡生成/校验。
- `web/backend/game_data/heartbeat_levels.json`：私有关卡索引。
- `web/frontend/src/pages/interactive-lab/`：入口、游戏、ECharts、类型/API 和样式。
- `web/backend/tests/test_heartbeat_hunter.py`、`web/frontend/tests/heartbeat-hunter.spec.ts`：真实规则和浏览器测试。
