# 第三阶段交互与边界测试

## 可复现命令与日志

```powershell
.venv\Scripts\python.exe -m pytest -q web/backend/tests --basetemp .test_tmp/phase3-http-final
.venv\Scripts\python.exe -m web.backend.validate_saved_models --samples-per-task 100 --output web/results/phase3_validation
npm --prefix web/frontend run typecheck
npm --prefix web/frontend run build
npm --prefix web/frontend run test:e2e
npm --prefix web/frontend run test:e2e -- --config playwright.production.config.ts
```

- 后端：`phase3_backend_final.log`，15 passed。包括真实读取/推理与 HTTP 边界。
- 模型复现：`web/results/phase3_validation/validation_summary.json`，600/600 类别匹配，最大概率误差 4.76837158203125e-07；未修改第二阶段验证产物。
- 类型：`phase3_typecheck.log`。生产构建：`phase3_build.log`。
- 最终 E2E：`phase3_e2e_final.log`。生产离线：`phase3_production_e2e.log`。以日志末尾为通过依据；iteration/targeted 日志属于调试记录。

## 覆盖范围

| 层级 | 场景 | 证据 |
| --- | --- | --- |
| 原回归 | 200、CNN/RF/LR、三模型、四分类、播放暂停继续、倍速、seek | workspace.spec.ts |
| 页面 | 三个分辨率真实数据截图、body 溢出、pageerror、HTTP 失败 | phase3.spec.ts |
| 答辩 | 八步、重复 CNN 真实请求、三模型、回放、任务切换、上一步、退出、全屏 | phase3.spec.ts |
| 图库 | 搜索、空结果、大图、报告、原图下载 | phase3.spec.ts |
| 竞态 | 延迟真实推理后快速切 CNN/RF/LR；播放中切 100；102 仅浏览 | phase3.spec.ts |
| 错误反馈 | 明确标记的测试注入 503、图像 404、30 秒超时与重试 | phase3.spec.ts |
| API 边界 | 不存在记录、负时间、越界、超过 30 秒、不支持导联、无预测片段 | test_phase3.py |
| 模型缺失 | 临时空目录建立 registry，六个工件均报错，返回可解释状态；未移动真实模型 | test_phase3.py |
| 标签范围 | N/V 不兼容 S；过滤保护区保留标注并跳过预测 | test_api_integration.py |
| 结果真实性 | 指标由最终计数复算，图库/报告 allowlist | test_phase3.py |
| 离线生产 | 阻断非 loopback 网络，浏览研究页、单拍、比较、回放 | production.spec.ts |

测试中注入的错误响应只用于验证故障反馈，未作为医学预测或正式页面数据。正常预测全部调用真实后端。

最终执行结果：开发回归 **9 passed、1 skipped（生产测试在独立配置执行）**；生产配置 **1 passed**。生产测试还实际点击了记录 200 的首个 N 类波形标注（样本 487，1.353 s），核对 Tooltip 样本位置与详情时间，并确认过滤保护区心拍不发出预测。截图为 `screenshots/phase3/waveform_real_marker_tooltip.png`。

## 已发现并修复

- 原工作台切换时间窗口/导联后可能保留旧选择与预测，比较和回放请求未取消。增加 AbortController、版本检查、互斥与统一状态清理。
- 先推理再判断心拍资格会对过滤边缘/任务外标注发出错误推理请求：改为先读取详情，再按 inference_eligible 决定推理。
- 回到起点前无已到达心拍时，清空未来心拍选择与预测。
- Umi 从 PORT 变量而非 --port 读取监听端口；修正开发入口，E2E 使用独立端口且不复用其它服务。
- 按钮图标进入可访问名称；测试对带图标的暂停/全屏按钮按可读名称匹配，避免误判。

浏览器控制台的开发器 topLevelAwait 目标兼容提示与 Ant Design 弃用提示单独记录；不等同于未捕获运行异常。最终声明以 pageerror、资源状态和实际交互为准。
