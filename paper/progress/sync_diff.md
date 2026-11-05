# 论文与项目同步差异报告

检查时间：2026-11-05T14:23:57+08:00（Asia/Shanghai）。

此检查只比较文件 SHA-256，不运行训练、推理、构建或测试，不自动改写论文、实验指标或图像。源码新增不等于功能完成；历史 passed 标记不等于本次测试。

基线时间：2026-11-05T14:23:55+08:00。

本次核对 433 个文件；新增 0，变更 0，删除 0。

## 新增文件

无。

## 内容变更

无。

## 删除文件

无。

## 需要人工处理的论文影响

未检出实验或 Web 证据的内容变化；这不代替科学复核或功能测试。

## 已用截图与对应页面

未发现已用截图的关联源码内容变化。已有截图仍是其记录日期的历史页面，不自动变为本次新截图。

## 覆盖范围

| 类型 | 文件数 |
|---|---:|
| dataset_metadata | 28 |
| dependency_or_web_config | 7 |
| deployment_validation | 6 |
| experiment_config | 2 |
| experiment_results | 119 |
| experiment_source | 46 |
| historical_web_evidence | 112 |
| model_artifact | 6 |
| paper_figure | 15 |
| paper_source | 5 |
| used_experiment_figure | 10 |
| used_screenshot | 3 |
| web_backend | 15 |
| web_config | 5 |
| web_frontend | 46 |
| web_test_source | 8 |

覆盖 src、configs、两数据集CSV/JSON、分类结果CSV/JSON/日志、六个正式模型、前后端源码/测试/配置/依赖、部署验证、保留的Web测试记录及正文图像索引指向的源图和论文副本。排除 node_modules、构建缓存、运行数据库和持续增长的服务日志。

哈希检查不能发现未纳入清单的临时文件、运行时行为差异或外部数据变化，也不会自动校验所有PNG是否仍与文字一致。源码关联采用保守路径映射；关联提示需要人工判断。
