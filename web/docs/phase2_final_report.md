# ECG-AI 第二阶段交付报告

## 范围

第二阶段增加 MIT-BIH 历史数据教学工作台：真实 WFDB 记录读取、专家标注浏览、复用既有训练工件的单拍与三模型推理、单拍形态对比、批处理历史回放、文档和自动化验收。没有新训练模型，也没有修改原始 ECG、预处理数据、划分文件、正式预测 CSV 或报告中的旧实验结果。

## 实际数据和接口

运行后从完整本地 `.dat/.hea/.atr` 清单动态建立记录目录；模型资格受现有 44 条受试者分组数据清单和 MLII 导联限制。其它完整记录可以看波形，不能调用模型。模型读取已有 N/V、N/S/V/F 的 LR、RF 和 1D-CNN 工件；接口回传模型哈希、任务类顺序、训练分区和推理耗时。窗口使用已验证的 253 点、-0.3/+0.4 秒、双向 0.5–40 Hz 过滤与训练集拟合归一化。历史片段内位于训练滤波保护区的标注会保留并展示，但跳过预测。

## 保存验证预测一致性

实际运行 `python -m web.backend.validate_saved_models --samples-per-task 100` 后：

- 验证样本：`web/results/phase2_validation/validation_summary.json`。
- 模型预测对照：`web/results/phase2_validation/validation_prediction_comparison.csv`。
- N/V 与 N/S/V/F 各取 100 条验证心拍。600/600 个预测类匹配；输入最大绝对误差 `0.0`，概率最大绝对误差 `4.76837158203125e-07`。

该核验的角色是部署路径复现既有 validation prediction；不是新性能评估。不得使用这份报告把已查看的正式 test split 称为未使用测试集。

## 自动化检查

2026-11-02 实际验收：backend pytest **6 passed**；前端 `tsc --noEmit` 通过；Umi production build 成功；Playwright Chrome 浏览器端到端 **1 passed**，覆盖真实服务健康检查、记录读取、单拍预测、CNN/RF/LR 切换、同拍比较、四分类切换、历史回放、暂停/继续、倍速和 seek。后端启动日志确认六个模型工件全部加载。

安装依赖时 npm 报告 **74 个审计告警**（10 low、46 moderate、17 high、1 critical）。本次没有直接运行 `npm audit fix`，以免自动改写 Umi/Ant Design 依赖组合；如要公开部署，需先单独确认受影响的依赖和可升级范围。本工作台当前定位为本地课程演示。

## 限制与课程演示说明

MIT-BIH 是历史研究数据。原实验按受试者分组，但类别覆盖稀疏，F/S 分布高度集中。标注是专家参考标签而不是模型特征；预测概率未作临床校准。服务仅面向本机教学演示，没有实时采集、告警、患者数据上传、访问控制或临床部署能力。操作和 API 细节见 `phase2_architecture.md`、`phase2_api.md`、`phase2_playback.md` 和 `phase2_demo_guide.md`。
