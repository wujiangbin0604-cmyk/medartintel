# 应用演示与公网验收

最终核验日期：2026年11月17日（北京时间）。

## 已完成的实际演示

在本机生产构建、FastAPI真实后端和Chrome无头浏览器上执行 `web/frontend/scripts/final-acceptance.cjs`，11项流程检查通过，页面异常0。游戏使用独立临时SQLite库，不改用户原有游戏历史。

1. 选择记录200，读取真实360 Hz MLII波形与专家标注。
2. 执行真实CNN推理，核对响应的保存工件来源和权重哈希。
3. 对同一采样点运行三个模型，并核对位置一致。
4. 注入一次明确标记的报告接口503，确认界面错误提示；移除故障注入后重试真实接口。
5. 通过浏览器实际下载JSON报告，核对心拍、专家标签、模型哈希、253点滤波窗口、三模型结果和训练侧归一化来源。
6. 加载真实历史片段并暂停回放。
7. 从旧测试N→S错误列表跳转实际ECG位置，重新执行真实推理。
8. 查看模型实验中心及图库。
9. 打开心跳猎人教程，主动开始挑战；后端返回真实记录109、360 Hz、3600点信号。未把这次开局当作学习效果试验。
10. 打开课程答辩演示路线，保存现场截图。

机器可读结果：`reports/demo_20261117/acceptance.json`。其中 `checks` 有11项；上述文字将有关步骤合并叙述，不是11个独立受试者试验。

真实截图位于 `reports/demo_20261117/`：`workbench_comparison.png`、`report_export_success.png`、`historical_playback.png`、`error_analysis.png`、`experiments.png`、`gallery.png`、`heartbeat-hunter.png`、`presentation_demo.png`。实际导出的 `ECG-AI_*_analysis.json` 同目录保存。图像没有重绘模型输出或修改预测值。

## 502诊断与公网验证

公开入口：[ECG-AI](http://47.83.150.55:8000/dashboard)。实际执行：

```powershell
.\.venv\Scripts\python.exe deploy/diagnose_public_demo.py
cd web/frontend
node scripts/public-acceptance.cjs
```

| 网络路径与检查 | 实际结果 |
|---|---|
| 当前配置网络出口 → `/api/health`、`/dashboard` | 均502，响应未给出源站Server信息 |
| 不使用该代理的直连 → 同一两个URL | 均200；健康响应为6/6模型就绪 |
| 直连 → 实际CNN推理 | 200，记录200、位置2331，预测N |
| 远程CNN工件SHA256与本地比较 | 一致：`5c4ff92e89f881d532eebf4b7f5fe6e6a240a5a88b820ca1d289e4af1fd78648` |
| Chrome直连公网页面 | 实际波形、真实单拍推理和三模型比较通过，页面异常0 |

证据：`reports/final_validation/public_probe.json`、`reports/demo_20261117/public_browser.json`、`public_demo.png`。同一目标配置出口502、直连200支持当前问题与网络路径有关，不能再据此前502直接认定服务器未启动、模型加载失败或CORS错误。未修改远程服务器，也未声称所有网络环境都可访问。

## 当前版本边界

公网仍为原有六模型版本。本轮新增报告导出与健康状态修复已在本地生产构建验收，随后按作者指令纳入GitHub同步（证据见`reports/repository_sync.md`），**尚未远程部署**。新RR研究候选没有替换原六个生产工件。公网成功不代表新本地功能已经上线。

健康状态的本地修复有明确失败测试：原实现模型缺失仍200；修复后仅6/6就绪返回200，否则503。修复已通过完整73项Python回归。

## 人工复查与课堂演示

1. 用浏览器直连上述公网地址；若特定代理返回502，换可直连网络复查，避免在已正常的源站上盲目改配置。
2. 展示本轮新功能时，使用本地 `start-local.ps1` 或既有Docker启动方式；待作者明确授权发布后，再部署新构建。
3. 依次演示记录200、专家标注、单拍推理、三模型比较、暂停历史回放、导出分析报告、错误列表及真实ECG定位。
4. 用 `reports/imbalance_experiments.md` 展示新训练结果；说明它们与界面原模型分开，且S误报/F漏分仍严重。
5. 不将模型分数称为临床概率，不把一次预测正确、软件测试通过或教学游戏积分当作患者泛化/临床效用/学习效果证据。
