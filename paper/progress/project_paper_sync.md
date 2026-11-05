# 项目与课程论文同步状态

核对日期：2026-11-05（Asia/Shanghai）。本文依据本地真实代码、现有实验工件和保留的历史软件测试记录撰写；未重新训练模型，也未在本次文稿工作中重新运行全套Web测试。

## 目前写入论文的成果

| 当前成果 | 论文位置 | 证据与同步要求 |
|---|---|---|
| 44记录、43受试者；201/202同组；31/6/6受试者划分 | 第二章；摘要 | metadata、split_manifest和独立重算审计；不可退回有误的旧派生计数 |
| 0.5–40 Hz连续离线滤波；253点标注窗口；训练集标准化 | 第二、三章 | 正式入口src/datasets/build.py及保存配置；旧48记录pipeline不能替代 |
| LR、RF、1D-CNN的两任务测试结果 | 第三至五章；摘要；总结 | 六个test预测CSV重算；已暴露历史测试，不宣称新盲测 |
| 类别不平衡、患者集中、验证集权重消融 | 第五章5.3、5.4 | 修正覆盖表、权重validation预测；变更须重核数据来源和协议 |
| train+validation的37受试者五折探索性CV | 第五章5.5 | 外折/OOF预测与训练日志；正式test患者不参与，仍非外部验证 |
| 真实错误心拍回顾 | 第五章5.6 | 明确区分不同错误案例选择表与波形图对应ID |
| 真实ECG、专家心拍定位、单拍推理、三模型比较、历史回放 | 第六章 | 前后端代码、历史E2E日志、2026-11-04截图；不是实时采集监护 |
| 实验中心、错误与泛化分析、科研图库 | 第六章 | 只读保存产物，页面数据/接口变化后核对截图与叙述 |
| 模型部署一致性600/600，最大概率差约4.77×10⁻⁷ | 第六章；摘要 | validation比较CSV/JSON和当前模型哈希；不等于100%分类准确率 |
| 动画、互动实验室、Heartbeat Hunter、首次欢迎教程 | 第六章简述 | 当前实现及2026-11-04历史验证；游戏分数不衡量医学诊断能力 |

## 尚未实现或尚未完成验证的工作

自动R峰检测、任意未标注ECG全流程自动识别、显式RR间期/节律上下文分支、多导联融合、外部数据库验证、临床概率校准均列为未来工作，不写成已完成。新增源文件本身不改变该状态。小时级稳定性、多用户并发及广泛移动设备组合验证也没有由现有短时测试完成。

## 已用截图与更新规则

正文图13、14、15分别采用2026-11-04 13:25阶段的工作台、三模型比较、实验中心实际浏览器截图。图题已注明阶段日期；这些画面早于当日下午互动入口与欢迎引导的添加，不能称作本次完整最新版截图。源文件路径、论文副本、正文位置见`paper/figures/figure_index.md`。

目前无需为证明已有核心界面而重新生成这些历史截图。若后续改变页面布局、选拍/推理流程、显示指标或论文描述，应运行相应场景并重新截图，更新图题日期与索引；若补充首页/欢迎/游戏画面，可选`web/docs/screenshots/welcome_onboarding/`及`heartbeat_hunter/`的真实截图，避免用欢迎中的装饰SVG充当真实ECG结果。

## 手动同步命令

在项目根目录或任意目录运行（使用本会话捆绑Python）：

```powershell
& 'C:\Users\20996\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'E:\医学人工智能\paper\tools\check_paper_sync.py'
```

脚本只读取关键项目文件并写`paper/progress/sync_diff.md`，比较新增、内容变更与删除，提示需复核的指标、方法、功能和截图。它不训练、不启动服务、不修改论文、不替换图像、不改任何实验数字，也不把新源码或passed标记直接转为完成结论。

首次基线在本次交付过程中显式建立，保存在`paper/progress/sync_baseline.json`。后续完成审阅、必要重算、测试和文稿更新后，才显式接受新基线：

```powershell
& 'C:\Users\20996\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' 'E:\医学人工智能\paper\tools\check_paper_sync.py' --baseline
```

`--baseline`只是接受文件指纹，不代表数据与结论已经科学核验。报告提示数据/模型改变时，可另外运行`paper/tools/audit_experiments.py`重新核验保存实验，核验后再人工决定是否更新论文。Web变化需选择相应接口与浏览器测试，保留日期和实际日志；当前欢迎文档的22项为历史分别运行计数，源码后增场景后不得继续充当最新套件项数。

## 证据导航

- 实验核验：`paper/evidence/experiment_audit.md`、`verified_metrics.json`。
- 系统审计：`paper/evidence/web_audit.md`。
- 文献：`paper/references/verified_references.md`、`references_to_verify.md`。
- 图像与结论来源：`paper/figures/figure_index.md`、`paper/evidence/claim_evidence_map.csv`。
