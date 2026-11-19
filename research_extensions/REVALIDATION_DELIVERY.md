# ECG-AI 本次交付与独立复核（2026-11-19）

本次发现 `E:/医学人工智能` 已有与请求对应的研究实现及完整实验，因其不在当前可写范围，保留原目录并迁入 `D:/生物信息学/medartintel-local` 进行复核和补充。原仓库 origin 为用户指定 medartintel，HEAD 为 `6fbb598802f1f4aa2f61b475798ab6cfb5299e9f`；首次只读 Git 检查已存在研究扩展、网页及部署修改和论文 QA 未跟踪文件。本次没有覆盖这些历史成果、没有提交或推送。

**来源界限：60 组正式训练为继承工件，本次没有重训这 60 组；本次真正执行的是所有权重的完整评价/校准推理复算、全部 RR 对齐复算、新的四模型训练 Smoke Test、拒识复算、13 对 PNG/SVG 重绘、Python 回归、前端构建和浏览器回归。**

## A. 工程交付

|内容|入口|
|---|---|
|RR 特征/掩码及逐拍追溯|rhythm_fusion/src/data.py；rhythm_fusion/data/alignment.csv / audit.json|
|独立 RRMLP 与 RhythmMorphologyCNN|rhythm_fusion/src/models.py；原 src/models/classifiers.py 保持原样|
|训练与模型加载|rhythm_fusion/src/run.py；results/*/fold*/seed*/A*/best.pt；web/backend/rhythm_lab.py|
|API|/api/rhythm/summary、/samples、/beat|
|实验室页面|web/frontend/src/pages/rhythm-lab/；路由 /rhythm-lab|
|教学联动|HeartbeatHunter 专家答案之后携带 record_id / annotation_sample 跳转实验室|
|本次新增审计工具|revalidate.py、revalidate_smoke.py、revalidate_analysis.py、delivery_20261119.py|
|本次最小改动|figures.py 支持独立输出目录；两份浏览器测试支持隔离截图/数据库；playwright.revalidation.config.ts|

本机启动：在副本根目录执行 `.venv/Scripts/python.exe -B -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8142`，访问 `http://127.0.0.1:8142/rhythm-lab`。本机 `.venv` 通过 .pth 读取原 E 盘环境依赖；独立机器应按仓库部署文档安装依赖。浏览器测试运行结束后会关闭测试服务。

## B. 真实实验结果

保持 44 条非起搏记录、43 个匿名患者组、201/202 合并及 31/6/6 原分区；新增研究只使用 train+val 的 37 组、86,286 拍。5 外层折 × 3 固定种子 × 4 模型，内部拟合/早停/阈值校准/外层评价患者互斥，最大 12 轮。下表为每个种子完整 OOF 指标的均值±种子样本标准差，不是患者置信区间。

|模型|Macro-F1|Accuracy|Balanced Accuracy|
|---|---|---|---|
|A0|0.3584 ± 0.0259|0.6337 ± 0.0298|0.4682 ± 0.0451|
|A1|0.3754 ± 0.0030|0.7819 ± 0.0051|0.4039 ± 0.0068|
|A2|0.4628 ± 0.0230|0.8032 ± 0.0158|0.5720 ± 0.0705|
|A3|0.3530 ± 0.0147|0.6698 ± 0.0147|0.4447 ± 0.0438|

|模型|类别|Precision|Recall|F1|支持拍数/患者数|
|---|---|---|---|---|---|
|A0|N|0.9499 ± 0.0105|0.6342 ± 0.0403|0.7600 ± 0.0276|77290/37|
|A0|S|0.0550 ± 0.0267|0.4514 ± 0.2335|0.0980 ± 0.0479|2751/28|
|A0|V|0.4596 ± 0.1090|0.7576 ± 0.0281|0.5652 ± 0.0806|5816/27|
|A0|F|0.0064 ± 0.0089|0.0295 ± 0.0391|0.0104 ± 0.0145|429/14|
|A1|N|0.9632 ± 0.0003|0.8178 ± 0.0057|0.8845 ± 0.0034|77290/37|
|A1|S|0.0297 ± 0.0086|0.1187 ± 0.0399|0.0475 ± 0.0142|2751/28|
|A1|V|0.4904 ± 0.0046|0.6759 ± 0.0208|0.5682 ± 0.0056|5816/27|
|A1|F|0.0008 ± 0.0002|0.0031 ± 0.0013|0.0012 ± 0.0002|429/14|
|A2|N|0.9724 ± 0.0020|0.8177 ± 0.0196|0.8882 ± 0.0111|77290/37|
|A2|S|0.1030 ± 0.0061|0.4060 ± 0.0504|0.1642 ± 0.0117|2751/28|
|A2|V|0.7029 ± 0.1031|0.8411 ± 0.0064|0.7629 ± 0.0568|5816/27|
|A2|F|0.0195 ± 0.0236|0.2230 ± 0.3136|0.0357 ± 0.0440|429/14|
|A3|N|0.9461 ± 0.0102|0.6779 ± 0.0200|0.7897 ± 0.0113|77290/37|
|A3|S|0.0475 ± 0.0283|0.3218 ± 0.2059|0.0828 ± 0.0497|2751/28|
|A3|V|0.4140 ± 0.0706|0.7761 ± 0.0223|0.5383 ± 0.0641|5816/27|
|A3|F|0.0008 ± 0.0007|0.0031 ± 0.0027|0.0013 ± 0.0011|429/14|

完整每折、每患者和错误转移分析见 [研究报告](INNOVATION_REPORT.md) 第5–6节及 `rhythm_fusion/results/cv_cpu_v1/summary.json`（含全部三种子）。S 类 50.02% 的支持来自同一患者，F 类 84.38% 来自同一患者；不能将大量心拍当作独立患者。

|A2 拒识代理|实际 Coverage|接受拍错误率|拒识拍真实错误率|错误检测 AUROC|
|---|---|---|---|---|
|max_score|0.8795 ± 0.0151|0.1611 ± 0.0102|0.4522 ± 0.0803|0.6812 ± 0.0339|
|entropy|0.8743 ± 0.0099|0.1635 ± 0.0060|0.4242 ± 0.1008|0.6557 ± 0.0540|

阈值来自每折内部独立校准患者的90%分位数，不保证新患者90%覆盖。逐类接受率、全体/保留分母召回、每患者拒识比例及描述性 Risk–Coverage 扫描均保存在 `uncertainty/results/revalidation_20261119/cv_cpu_v1/summary.json`；与继承结果逐字段完全相同。

## C. 当前能成立的结论

当前开发患者及短预算内，A2 相对 A0 的 OOF Macro-F1 平均提升 0.1044，三个种子均提升；同容量 A3 未保留收益，支持有效节律对应关系具有信息价值。RR-only 有独立判别力，但整体不及融合。每个种子 30–31/37 患者固定四类F1改善，4–5患者下降，仍存在患者异质性。

S 类 Precision/F1 改善，但 Recall 均值下降约0.0453且种子波动明显；F 类 F1 仍仅约0.0357，不能称已解决 S/F 识别困难。不确定性代理对错误有有限排序能力，拒识后全体预测并未变得更准确，不能称为临床风险概率。

创新是既有轻量融合方法的可审计实现、受控消融和患者隔离的教学集成；原项目此前已有4维RR＋focal分支，不可主张首次CNN＋RR。波形右侧窗口及双向滤波为离线条件，专家定位不等于端到端异常发现。

未执行：新增 N/V 四模型重复、外部数据库/前瞻性验证、临床阈值、概率校准、长预算敏感性、自动QRS误差/真实缺失节律效果实验。网页 N/V 显示空状态。当前适合撰写如实限定的课程扩展章节，不能作独立外部验证或临床有效性主张。原课程论文不变，新增章节草稿见 [PAPER_CHAPTER_DRAFT.md](PAPER_CHAPTER_DRAFT.md)。

## D. 本次真实测试与保护

Python：96项，失败0，错误0，跳过0；浏览器：15通过，失败0，跳过0。构建与 setup 后 TypeScript 检查退出码0。
保护清单：1042文件，变化0；所有60个checkpoint权重、scaler、源代码fingerprint、分组和概率已复核。所有86286行RR/掩码对照原始标注重新计算。本次未打开原 test.npz。

保留失败证据：初次沙箱内 TestClient 在34项后被本地socket限制挂起并中止，未计通过；本机重跑通过。首次类型检查因副本未生成 .umi 导出失败，执行 Umi setup 后通过。原始失败记录未删除。

|本次命令记录|退出码|耗时秒|
|---|---|---|
|[revalidation_20261119_analysis](validation/revalidation_20261119_analysis.json)|0|22.97|
|[revalidation_20261119_artifact_command](validation/revalidation_20261119_artifact_command.json)|0|69.48|
|[revalidation_20261119_browser_command](validation/revalidation_20261119_browser_command.json)|0|125.57|
|[revalidation_20261119_final_protection](validation/revalidation_20261119_final_protection.json)|0|1.74|
|[revalidation_20261119_fresh_smoke](validation/revalidation_20261119_fresh_smoke.json)|0|14.50|
|[revalidation_20261119_frontend_build](validation/revalidation_20261119_frontend_build.json)|0|53.54|
|[revalidation_20261119_protection](validation/revalidation_20261119_protection.json)|0|11.34|
|[revalidation_20261119_python_local](validation/revalidation_20261119_python_local.json)|0|19.49|
|[revalidation_20261119_typecheck](validation/revalidation_20261119_typecheck.json)|2|31.88|
|[revalidation_20261119_typecheck_after_setup](validation/revalidation_20261119_typecheck_after_setup.json)|0|6.93|
|[revalidation_20261119_umi_setup](validation/revalidation_20261119_umi_setup.json)|0|7.84|

新增图表：`rhythm_fusion/figures/revalidation_20261119/`，13对PNG+SVG及catalog.json；浏览器截图：`validation/revalidation_20261119_browser/screenshots/`；完整权重复算：`validation/revalidation_20261119_artifacts.json`；本次新增文件哈希清单：`REVALIDATION_FILES.csv`。

复核命令：`.venv/Scripts/python.exe -B -m research_extensions.revalidate --full`；新Smoke入口 `-m research_extensions.revalidate_smoke`（拒绝覆盖已存在目录）；分析重绘入口 `-m research_extensions.revalidate_analysis`；浏览器命令在web/frontend下为 `node node_modules/@playwright/test/cli.js test --config playwright.revalidation.config.ts`。

生成时间：2026-11-19T14:48:56.133730+08:00
