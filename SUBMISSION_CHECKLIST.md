# 医学人工智能最终提交检查清单

作者：吴江彬；学号：102400329；核验日期：2026年11月17日。方框只表示已实际完成的事项。

## 材料

- [x] 最终论文DOCX：`paper/final/ECG_AI_课程论文_最终优化版V3.docx`。
- [x] 同版PDF：`paper/final/ECG_AI_课程论文_最终优化版V3.pdf`。38页，正文13309个汉字；Word实际打开、目录域刷新并导出，全部页面检查通过。
- [x] 最新源稿：`paper/draft/ECG_AI_课程论文_最终优化版V3.md`；质量证据：`paper/qa/v3/final_quality_check.json`。V1/V2为历史保留件，不要误当最新附件。
- [x] 项目源码、必要依赖和使用说明：工作区内`src/`、`configs/`、`web/`、`requirements*.txt`、`README.md`、`DEPLOY_LOCAL.md`；生产前端已构建。
- [x] 原六模型：`checkpoints/nv44_v1/formal/`与`checkpoints/nsvf44_v1/formal/`；原始MIT-BIH：`data/mitdb/`，48条。训练NPZ可按README从原始数据离线重建。
- [x] 新研究工件：`results/controlled_imbalance_20261116/runs/`含12组检查点、训练记录和逐拍预测；`protocol.json`、`selection_locked.json`、`test_evaluation.json`及汇总CSV同目录。它们没有替换原六模型。
- [x] 审计与实验报告：`reports/cnn_generalization_audit.md`、`model_stability_audit.md`、`imbalance_experiments.md`。
- [x] 真实演示截图及下载报告：`reports/demo_20261117/`。答辩可用`workbench_comparison.png`、`report_export_success.png`、`error_analysis.png`、`heartbeat-hunter.png`、`presentation_demo.png`；公网截图为`public_demo.png`。
- [x] 测试报告与日志：`reports/final_test_report.md`、`reports/final_validation/`；演示报告：`reports/application_demo_check.md`；最终评分：`FINAL_REVIEW.md`。
- [x] 公共仓库当前存在并可读取：[GitHub项目](https://github.com/wujiangbin0604-cmyk/medartintel)，默认分支main、public。
- [ ] **本轮源码、实验工件/结果、最新README和论文对应材料的公开同步与读回。** 已按作者指令启动同步，完成证据及提交见`reports/repository_sync.md`；核对成功后更新此项。服务器仍是原版本，旧ZIP也不是本轮交付版。
- [ ] 若需按通常开源许可授予使用权，由作者确认合适许可证及第三方材料说明；本轮未代为作法律许可决定。
- [ ] 作者确认本项目和论文没有作为另一门课程的相同或实质雷同作业重复提交；未用未知情况替代确认。
- [ ] 作者阅读最终论文、核对个人信息与引用、能够解释真实实验和失败结果，并完成所需原创性核验。

## 邮件与收件确认

- [ ] 在**北京时间2026年12月15日23:59前**发送，以邮件发送时间为准。
- [ ] 收件人严格为：`huanhu@fzu.edu.cn`。
- [ ] 标题严格为：`102400329_吴江彬_医学人工智能`，不加其他前后缀，不变更顺序。
- [ ] 附件选用上述V3课程论文；通知未限定DOCX/PDF二选一，可同时附上二者，避免误附V1/V2、临时截图或训练代码压缩包。
- [ ] 参加拓展考核时，在邮件正文写入可公开访问且已同步正确版本的GitHub/Gitee仓库链接，无须发送代码附件。公网演示地址可作为补充，不能代替代码仓库链接。
- [ ] 检查附件实际打开、仓库匿名可访问、README启动命令及必要模型可获取，确认论文中新增结果能追溯到公开工件。
- [ ] 发送后主动通过QQ联系任课教师，确认邮件已经收到；保留实际回复，不能把“已发送”当作“已收件”。

本轮GitHub同步经作者明确授权，结果见`reports/repository_sync.md`；本清单没有执行邮件发送、QQ消息或远程部署。检查通过的软件功能不等于临床诊断能力；新RR方案仍有S误报和F漏分，答辩应如实说明。
