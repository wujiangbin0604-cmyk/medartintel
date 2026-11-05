# 保存模型与推理服务一致性核验

## 验证方法

`backend/validate_saved_models.py` 对 N/V 与 N/S/V/F 既有 validation split 分别确定性选择最多 100 条样本，按专家标签做近似均衡抽样。使用同一 API 服务读取本地 WFDB 信号、标注位置、连续滤波、训练集归一化和已保存模型，再与原 `val_predictions_all_models.csv` 的类别和逐类概率对齐。

通过条件：同一 `sample_id` 和模型预测类一致，最大概率绝对差不超过 `1e-5`，推理标准化向量最大绝对差不超过 `1e-5`。结果只证明部署路径与已有验证预测相符，不表示模型性能已经改善或具有临床有效性。

## 数据隔离

运行过程只读取 `val.npz`、验证预测 CSV、验证元数据、模型工件、处理配置和原始记录。它不读取正式测试 NPZ 或测试预测文件做选型、阈值设置或调参。正式测试数据曾在原课程实验中查看；不能再描述为“本工作台未触碰的独立外部测试”。

## 自动生成结果

2026-11-02 在最终 API 服务代码上完成：每任务 100 条（N/V 为 N=50、V=50；N/S/V/F 为 N=32、S=25、V=25、F=18），共比较 200 条验证心拍 × 3 模型 = **600** 条模型输出。600/600 个预测类相同；归一化输入最大绝对误差为 **0.0**，概率最大绝对误差为 **4.76837158203125e-07**，均小于 `1e-5` 门槛。模型 SHA-256 和类别顺序保存在机器生成 JSON。

逐条结果：`web/results/phase2_validation/validation_prediction_comparison.csv`；确定性样本清单：`web/results/phase2_validation/validation_sample_manifest.csv`；机器汇总：`web/results/phase2_validation/validation_summary.json`。如果将来任何输入、类别或概率差异超出阈值，验证脚本会失败并保留定位信息。
