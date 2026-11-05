# ECG-AI 第三阶段交付报告

执行日期：2026-11-03。延续原项目，未训练模型、修改原始 WFDB、改写原正式实验结果或用 Mock 替代预测。

## 已交付

| 页面 | 路由 | 内容 |
| --- | --- | --- |
| 项目总览 | /dashboard | 真实记录数、心拍数、模型状态、类别/分区分布、两项任务性能、工作流、可点击入口 |
| ECG 工作台 | /ai-detection | 波形主区、标注选择、真实单拍推理、三模型、形态对照、回放、紧凑屏详情 Drawer |
| 实验中心 | /experiments | 二/四分类 Tabs、指标、Support、交互矩阵、行归一化、实际训练曲线与最佳 Epoch |
| 泛化分析 | /generalization | 患者热力图、集中度、误分类、权重消融、五折患者 CV 与筛选 |
| 科研图库 | /gallery | 本地 157 张图、分页/筛选/搜索、大图、报告和下载、错误提示 |
| 答辩模式 | /presentation-demo | 八步引导、真实记录 200、CNN/三模型/回放、全屏与退出 |

新增只读研究接口从已有最终核验 CSV、训练日志和本地图像目录读取；图像与报告通过 allowlist 提供。工作台保留所有原核心功能，并修复取消、竞态、回放状态和字体可读性。

## 实际验收状态

| 检查 | 状态 |
| --- | --- |
| 后端回归 | 通过（对应日志已生成） |
| 验证预测 600/600 | 通过（对应日志已生成） |
| TypeScript | 通过（对应日志已生成） |
| 生产构建 | 通过（对应日志已生成） |
| Playwright 完整回归 | 通过（对应日志已生成） |
| 生产离线验证 | 通过（对应日志已生成） |

最终测试汇总：后端 **15 passed**；开发 E2E **9 passed、1 skipped**；被跳过的生产用例通过独立配置执行为 **1 passed**。21 张桌面页面截图覆盖三个分辨率，另有 8 张答辩步骤截图和真实标注 Tooltip 截图；三份浏览器检查 JSON 的未捕获异常、失败资源均为 0。

依赖审计：74 → 71 项，残留 critical 1 / high 16；已记录在 [安全审计](security_dependency_audit.md)，没有宣称零风险。

## 文档与产物

- [设计系统](phase3_design_system.md)
- [真实截图与审查记录](phase3_visual_review.md)
- [交互/边界测试](phase3_interaction_testing.md)
- [安全审计](security_dependency_audit.md)
- [实际性能](phase3_performance_report.md)
- [答辩指南](phase3_demo_guide.md)
- 截图：`screenshots/phase3/`；三种桌面尺寸与答辩流程。
- 600 次模型复现：`web/results/phase3_validation/`。

## 运行

根目录运行 `npm --prefix web/frontend run build`，随后 `.venv\Scripts\python.exe -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8002`。打开 `http://127.0.0.1:8002/presentation-demo`。

## 已知限制

- 71 项依赖告警仍需 Umi 插件生态的独立升级工作；不公开开发服务。
- 本轮只验证浅色主题。长内容纵向滚动，图库原图保持原研究配色与内容。
- 性能为本机少量采样与短时内存观察，不是长时间无泄漏或生产并发保证。
- 历史 test 已在原研究查看；四分类 S/F 支持量与患者分布不均，不能包装为临床可用性。
- 图库/研究文件缓存随服务进程生存；外部新增或修改文件后需重启服务刷新。
