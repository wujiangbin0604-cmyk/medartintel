# Heartbeat Hunter 测试记录

日期：2026-11-04。使用项目已有 Python 虚拟环境、Node、真实本地 MIT-BIH、已训练模型和无头 Google Chrome。没有使用合成 ECG 替代真实数据。

## 实际结果

| 验证 | 结果 |
|---|---|
| TypeScript `npm run typecheck` | 通过，退出码 0 |
| Umi 生产构建 `npm run build` | 通过，退出码 0 |
| 全部 `web/backend/tests` | **37 passed**，4.43 s |
| 游戏 Playwright 生产构建 E2E | **10 passed**，1.5 min |
| 62 个关卡完整校验 `--check` | 通过，原始文件哈希、专家符号、窗口、安全区域均匹配 |
| 三种分辨率 | 1920×1080、1440×900、1366×768 均通过实际浏览器检查 |
| 截图 | `web/docs/screenshots/heartbeat_hunter/` 内 23 张真实浏览器 PNG |
| 帧间隔采样 | 3 s / 537 个 rAF 帧，median 5.6 ms，P95 5.7 ms，>50 ms 为 0 |
| 稳定性 | 同一会话连续 10 次离开/进入页面，正确恢复、单个图表 canvas、无 pageerror |

第三方 WFDB/Pandas 与 Starlette/AnyIO 有既有弃用警告，未导致测试失败。本次未升级依赖或更改训练代码。

## 后端覆盖

新增 20 个测试实例，和原有 17 个后端测试一起运行：

- 全部真实关卡逐个核验、start 原始物理信号逐点比对。
- config/start/session 未结束响应不含答案和标签。
- 全对、N 误选、未匹配点击、漏选、连击及时间奖励。
- 完全重复/邻近重复、同一参考心拍只匹配一次、±36 样本边界及 ±37 样本不匹配。
- 重复提交幂等；同一下一关请求幂等；五关不重复。
- 截止前检查点、截止后拒绝修改、2 s 固定宽限、超时零时间奖励。
- 服务端暂停/恢复延长时间；标准/挑战禁止暂停。
- 挑战只能选择已播放位置、倍速回放位置连续。
- 无效会话、非法 sample_index、浮点/字符串/布尔值输入拒绝。
- SQLite 重新打开恢复、匿名个人历史、放弃过期会话不记成绩。
- 原有 ECG、推理、回放和研究 API 回归。

## 浏览器 10 个场景

1. 实验室入口 → 新手 → 真波形 → 选择/取消 → 服务端暂停/恢复 → 提交 → 连击 → 成绩单 → 三模型真实对比 → 刷新 → 下一关 → 重玩 → 历史。
2. 真实 ECharts 像素坐标点击 → 清空 → N 误选 → 验证真实负分与漏选。
3. 标准模式隐藏候选、倒计时变化、禁止暂停、点击、滚轮缩放、最后 10 秒强调、超时自动结算。
4. 挑战模式 rAF 回放位置真实推进、服务端 2× 速度、离开页面删除图表、重新进入恢复同一会话。
5. reduced motion 下隐藏扫描、503 网络错误提示与重试、音效开关/音量控制、空答案完整结算、结束后禁用提交。
6–8. 1920、1440、1366 下实验室/准备/选择/结果截图，无横向溢出，原 ECG 工作台实际 canvas 加载。
9. 真实挑战回放中 3 s 帧间隔采样。
10. 十次 SPA 路由往返，恢复会话，图表清理，无页面异常。

超时 E2E 通过测试进程直接缩短**独立测试 SQLite 中本次会话**的 deadline，避免在每次运行中空等 90 s；生产没有测试用改时 API。后端超时规则另有可控服务器时钟测试。游戏答案由测试进程读取后端私有索引作为断言依据，浏览器应用从未在答题前请求索引。

## 视觉检查与修复

实际查看了实验室、1920 选择、1440 结果、连击等截图。修复：

- 给主操作按钮明确 aria-label，避免图标名称混入无障碍名称。
- 音量名称正确传给 Slider 手柄。
- 倒计时先取整再拆分钟/秒，修复跨分钟显示。
- 缩短右栏文案、收紧间距，减少中央留白。
- 子页面保持实验室导航高亮，增加可点击 Heartbeat Hunter 子入口。
- 截图等待波形和选择动画稳定；单独捕捉真实 Combo 反馈。

性能数字只代表此机器、此次无头 Chrome 的短期采样，不是所有设备的帧率保证；十次页面往返也不等同于数小时、多用户或移动设备压力测试。音效通过 Web Audio 合成与 UI 开关验证，没有把人工听音或外部音频素材审计称为已完成。

## 复现

在 `E:\医学人工智能`：

```powershell
.\.venv\Scripts\python.exe -m web.backend.build_heartbeat_levels --check
.\.venv\Scripts\python.exe -m pytest web/backend/tests -q --basetemp .test_tmp/hunter_verify
```

在 `E:\医学人工智能\web\frontend`：

```powershell
npm run typecheck
npm run build
npx playwright test --config playwright.hunter.config.ts
```

E2E 使用专用端口 8136、数据库 `web/runtime/hunter_e2e.sqlite3`，不会覆盖个人实际体验记录。
