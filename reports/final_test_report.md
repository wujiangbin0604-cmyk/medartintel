# 最终自动化验收报告

日期：2026年11月17日（北京时间）。只将实际执行成功的检查记为通过。

## 命令、结果与证据

命令在项目根目录执行；前端命令的工作目录为 `web/frontend`。`node`指本轮实际使用的bundled Node 24.22.1；训练与接口使用项目Python 3.12.10环境。

| 检查 | 实际命令 | 实际结果 | 日志或结果 |
|---|---|---|---|
| 原有基线 | `python -m pytest tests web/backend/tests deploy/update/tests -q -p no:cacheprovider`（新增代码前） | 58 passed | `baseline_tests.log` |
| 全量稳定性审计 | `python -m src.evaluation.stability_audit` | 两任务完整性通过；原始来源哈希不变；全部旧CNN val/test类别一致 | `results/stability_audit_20261116/audit.json` |
| 新实验训练 | `python -m src.evaluation.controlled_imbalance --stage train` | 4方案×3seed完成；仅val选型，检查点冻结 | `imbalance_train.log`；`selection_locked.json` |
| 预定最终测试阶段 | `python -m src.evaluation.controlled_imbalance --stage final` | 12组一次预定评估阶段完成；旧测试探索性复用 | `imbalance_final.log`；`test_evaluation.json` |
| 独立指标汇总 | `python -m src.evaluation.controlled_report` | 逐拍CSV复算及选择哈希核对通过 | `controlled_*summary.csv` |
| 真实IG | `python -m src.evaluation.final_explanations` | 4个验证样本；真实检查点；完整性相对误差约0.09%—0.17% | `explanations.log`；IG manifest |
| 新报告接口 | `python -m pytest web/backend/tests/test_inference_report.py -q` | 3 passed | `report_api_tests.log` |
| 健康修复前复现 | `python -m pytest web/backend/tests/test_health_readiness.py -q` | **预期红灯：1 failed、1 passed**；缺失模型仍200 | `health_before.log` |
| 最终Python回归 | `python -m pytest tests web/backend/tests deploy/update/tests -q -p no:cacheprovider` | **73 passed，68 warnings，6.00秒** | `final_tests.log` |
| 前端类型 | `node node_modules/typescript/bin/tsc --noEmit` | 退出码0 | `typecheck.log` |
| 前端构建 | `node node_modules/@umijs/max/bin/max.js build` | 退出码0，生产页面实际运行 | `frontend_build.log` |
| 本机浏览器 | `node scripts/final-acceptance.cjs` | 11项流程检查通过，页面异常0，真实报告下载 | `browser_acceptance_final.log`；`acceptance.json` |
| 公网HTTP | `python deploy/diagnose_public_demo.py` | 配置出口502；直连健康/首页/真实推理200，工件哈希一致 | `public_probe.json` |
| 公网浏览器 | `node scripts/public-acceptance.cjs` | 真实波形、推理及三模型比较通过 | `public_browser.log`；`public_browser.json` |
| 依赖一致性 | `python -m pip check` | No broken requirements found | 本轮终端实际输出；没有安装或更换训练依赖 |
| 论文生成/Word导出/逐页检查 | bundled Python构建、`word_export.ps1 -UpdateCopy`、`render_final_v3.py`、`check_final_v3.py --confirm-visual` | **38页全部渲染与人工逐页检查；42项目录页码一致；7个原生公式、17表、20图形对象；正文13309汉字** | `paper/qa/v3/final_quality_check.json`；`paper_quality.log` |
| 原文件保留 | `check_final_v3.py --confirm-visual`中的独立SHA256核对 | **164项历史模型/结果/论文全部未变** | `results/final_optimization_20261116/preservation_check.json` |
| 公共仓库同步 | GitHub连接器读回main引用、提交、完整递归树及更新后README | 工件提交`6f9fcef`：远程1732个Git文件对象全部匹配，含12个新检查点、V3 DOCX/PDF及新README；发布前1012项部署依赖与暂存字节一致 | `repository_sync_20261117.json`；`repository_check.json`保留同步前记录 |
| 发布文件与真实API | `python -B deploy/ubuntu22/build_release.py --manifest-only`；`python -B deploy/ubuntu22/verify_bundle.py --api http://127.0.0.1:8144` | **1011项文件哈希通过，48条原始记录、62游戏关卡、6模型就绪、3600点真实信号；18项固定参考预测全部匹配**；只刷新清单，未创建/覆盖旧ZIP | `deploy/ubuntu22/package_validation.json` |

日志归档在 `reports/final_validation/`；科学结果和浏览器结果按表中目录保存。测试警告主要为WFDB/Pandas和Starlette/AnyIO弃用提示，没有当作测试失败，也没有隐去它们。

## 修复与再次验证

- 模型性能反差：原始信号、索引、划分、归一化和工件重推核验通过；差异仍存在，没有通过删患者或改数字“修复”。已转化为明确的患者组成与稳定性限制。
- 新增报告：后端从真实三模型重新推理生成来源可追溯报告；新增3项回归通过。浏览器先做明确标记的503故障注入，再移除注入、实际下载并核对真实数据。
- 健康接口：失败测试证实原实现未就绪仍200；现在缺失模型返回503，6/6就绪返回200；完整73项回归通过。
- 初次受限网络环境下的未完成运行不算通过；最终接口与浏览器检查在允许所需本地通信的执行环境中完成。
- 最终发布清单API核对初次也被本机套接字策略阻止（WinError 10013），该次不计通过；在允许本地通信的执行环境再次执行，1011文件与18项真实参考预测均通过。烟雾测试使用本轮隔离游戏数据库，不更改原始数据或模型。
- 论文首轮渲染发现空白页和重复页码，已通过分节、独立页脚与PAGE计算篇眉修复。WPS模板含两个Normal定义，仅改其中一个会在Word合并时恢复两字符缩进；最终同时清理两者，表格样本数完整显示。E盘空间不足曾使Word保存失败，改用另一已授权目录中的临时副本实际保存/导出后回写终版；最终DOCX/PDF哈希与38页逐页检查闭环通过，失败导出未作为成功证据。

## 没有执行或不能据此推出的事项

- 未执行新的临床/外部患者验证、学习效果用户研究或全文查重。
- 未在当前Windows机器上执行Linux Docker Engine构建，不能声称容器验收通过。
- 未运行所有历史浏览器套件；本次运行的是新增的11项生产流程检查和公网真实交互脚本。
- 未把三随机种子标准差当作独立患者置信区间，未根据本轮测试结果再选模型或种子。
- 原验收时未推送仓库；随后按作者明确指令同步（见`reports/repository_sync.md`）。未远程部署本轮修改、未发送邮件、未伪造QQ收件确认。
