# E盘空间耗尽与恢复

2026-11-18 本地重复种子训练运行到18/40个完整job后，E盘可用空间降至0（总85,898,293,248字节），保存checkpoint失败并退出1。原游戏完整浏览器回归同时因ENOSPC退出1（当时仅2/10通过），不计作全套通过。原日志分别保存在 repeated_seed_training.txt、hunter_browser.txt。

只清理本次新建的 `web/frontend/test-results-rhythm` 追踪缓存（约59MiB）；删除前解析绝对路径并验证位于E:/医学人工智能且目录名精确匹配。保留所有实际实验工件、原日志、截图、原始数据、原论文、原模型和用户文件。释放约61.6MB。

浏览器临时追踪目录改到系统临时目录（可用环境变量ECG_E2E_OUTPUT覆盖），游戏完整回归禁用trace，仍保存JSON结果、日志和最终截图。数据NPZ尝试NTFS无损压缩，但该卷未实际压缩任何文件，文件字节未变。

从完成标记及SHA校验继续训练：已完成job跳过，未完成job按相同固定种子重启。实际恢复日志 repeated_seed_training_resume.txt。最终完整性以最终测试、模型清单及 protection_verification.json 为准。
