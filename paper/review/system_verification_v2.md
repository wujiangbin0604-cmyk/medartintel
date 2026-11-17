# V2 系统实现与证据复核

复核日期：2026-11-06（Asia/Shanghai）。职责为第六章实证补充，不修改V1、实验工件或Web代码。本轮读取了第二轮任务附件、现有系统审计、前后端源码、保存验证CSV/JSON、历史测试日志和实际PNG；本轮未启动服务、未重新执行软件测试、未训练模型。

## 相对V1的实际变化

以`paper/progress/sync_baseline.json`（captured_at=2026-11-05T14:23:55+08:00）为V1指纹依据，重新计算其已跟踪的前端src、后端、路由相关63项文件SHA-256，未检出内容变化。`.umirc.ts`当前路由仍包括`/dashboard`、`/ai-detection`、`/ai-inference`、`/experiments`、`/generalization`、`/gallery`、`/presentation-demo`、`/interactive-lab`及`/interactive-lab/heartbeat-hunter`。这是对已有跟踪项的结论，不替代所有运行时功能测试。

当前InferenceService仍从ECGStore取得标准化真实窗口，再调用Model Registry。research模块仍读取`results/classification`的最终核验CSV、逐模型test预测和保存训练历史；图库读取项目`figures/`；游戏读取真实关卡索引和WFDB并单独保存匿名会话。没有发现把新论文的V2统计输出接入网页的变更，不应将本轮论文深化误写为新的Web功能开发。

## 验证文件定位与差异

`web/results/phase2_validation/`和`phase3_validation/`都真实存在，各含comparison、sample_manifest、summary三文件。V1引用phase2并非路径错误。V2统一采用较后阶段的phase3作为表格来源，`web/docs/phase3_model_validation.log`保留对应历史运行输出；文件保存时间为2026-11-03。验证脚本默认输出仍是phase2，命令可通过`--output`指定其他目录。

两阶段sample_manifest和summary的SHA-256相同，comparison CSV的SHA-256不同。按(task,model_id,sample_id)对齐，600个键相同、预测类别相同；差异出现在约1e-16量级的RF浮点概率误差记录，不是样本或类别结果改变。不能声称三个文件全都字节相同，也不能将phase3称为新独立样本验证。

本轮读取phase3 CSV重新汇总为：

| 任务 | 模型 | 条数 | 类别一致数 | 概率最大绝对差 | 输入最大绝对差 |
|---|---|---:|---:|---:|---:|
| nv | logistic_regression | 100 | 100 | 2.980232238769531e-07 | 0.0 |
| nv | random_forest | 100 | 100 | 2.220446049250313e-16 | 0.0 |
| nv | cnn_1d | 100 | 100 | 1.6295221005879768e-07 | 0.0 |
| nsvf | logistic_regression | 100 | 100 | 4.76837158203125e-07 | 0.0 |
| nsvf | random_forest | 100 | 100 | 2.220446049250313e-16 | 0.0 |
| nsvf | cnn_1d | 100 | 100 | 3.284582973384076e-07 | 0.0 |

汇总与JSON一致。当前六模型工件SHA-256仍全部匹配summary记录。脚本只读保存的val数据及val预测构建对照；本次汇总没有重新进行API推理。模型标签序列NV=[N,V]、NSVF=[N,S,V,F]可由Model Registry及summary双重核对。

### 跨任务心拍重叠与计数单位修正

2026-11-06最终复核中，直接从`phase3_validation/validation_sample_manifest.csv`以`(record_id, annotation_sample)`构造两任务位置集合，得到N/V集合100个、四分类集合100个、交集57个、并集143个；交集为N类32个、V类25个。manifest的200行共有6个不同subject_id。200是任务—心拍条目计数，600是这些条目在三模型上的输出对照次数，143才是跨任务不同实际心拍位置数；同一受试者的不同心拍也不能视为完全独立的患者证据。

先前分工补充稿把200行写成“独立选取的心拍共200条”，没有处理任务间重叠，现已修正补充稿并通知主流程同步主稿。该修订是计数单位和证据独立性解释的来源修正，不改动600/600或任何概率误差结果，不改变原始manifest、comparison或实验产物。新增对应证据表为`paper/evidence/claim_evidence_v2_system.csv`，来源修改也追加在`revision_log.md`。

## 历史测试证据的可写范围

- 第五阶段原始`web/docs/visual_fidelity/backend_final.log`：18 passed、52 warnings、2.03 s；`e2e_final.log`：16 passed、5.2 min；`production.log`：1 passed、26.9 s。各文件对应不同套件，不合并为本次统一通过项数。
- `typecheck.log`和`build.log`分别保留类型检查命令与生产构建日志，交付报告记载通过。本轮未重跑。
- 游戏报告记载2026-11-04后端37项及游戏E2E10项通过；历史`.last-run.json`为passed但没有项数或代码哈希，不把报告等同完整原始日志。
- 欢迎报告的22项为当时分别运行的原游戏10、欢迎11和追加平台1。当前spec后来增加普通HTTP匿名ID兼容场景，静态展开为13个欢迎相关场景加10个游戏场景；没有本轮新运行结果，不宣布23项当前通过，也不将旧22项当最新总项数。
- UI存在、历史测试通过、部署一致性、模型分类性能、临床效用及学习效果是不同证据层次。功能验证表按模块列出历史覆盖，不把套件总数复制为各模块独立通过数。

## 现有服务与重截图可行性

只读检查`Get-NetTCPConnection -State Listen`未返回可用监听项；定向检查8000、8001、8002、8136、8138、8139、8140未检出监听。`web/runtime/hunter_server.pid`保留35860，但`Get-Process -Id 35860`未找到进程；对应stderr日志最新记录为2026-11-04 17:08。PID文件不能证明服务仍在运行。该结果限于本轮可见环境，不断言用户的其他环境没有服务。

因此本轮未复用活服务新截屏，也未按本分工自行启动服务。保留原始真实截图并进行合理无损裁剪；如主流程后续获得现有服务或启动并验证服务，可另采真实截图替换，但不得把本轮副本标作2026-11-06新运行画面。

## 三张局部图的溯源与裁剪

源图均位于`web/docs/visual_fidelity/iteration2/`，2026-11-04 13:25保存，早于当日下午新增欢迎/互动入口；剪裁的核心功能源码相对V1指纹未变。图题可简化，统一在图注交代日期和局部处理。

| 新文件 | 真实源文件 | 原图尺寸 | 无损裁剪框(left,top,right,bottom) | 结果 |
|---|---|---|---|---|
| `paper/figures/v2/system_workbench_crop.png` | `ecg_1672x941.png` | 1672×941 | (512,132,1334,618) | 822×486；完整保留波形坐标轴、单位、来源与选拍 |
| `paper/figures/v2/system_comparison_cards.png` | `comparison_1672x941_full.png` | 1672×1116 | (246,763,703,951)；(714,763,1171,951)；(1182,763,1639,951) | 三张457×188卡片以12像素间距纵向重排，457×588 |
| `paper/figures/v2/system_experiments_class_crop.png` | `experiments_1672x941_full.png` | 1672×1831 | (950,715,1653,984) | 703×269；完整表头、N/V支持和指标、解释提示 |

图像仅使用Pillow裁剪和白底拼接，无AI图像编辑、波形重绘、数值替换或内容补绘。原图未修改，三张副本已实际打开检查；结果无裁切或重叠。比较卡片保留原模型名、类别、概率、耗时、参考一致性和版本。其99.6%/100%/98.1%是该单拍的模型概率显示，不是总体分类准确率；建议图注明确。

## 待主流程落实

1. 并入`paper/draft/v2_system_additions.md`中的架构、推理、模块验证表和六组部署一致性表；避免与V1重复讲述。
2. 按最终图序登记三张副本及裁剪来源；卡片图建议9—10cm宽，其他两图按正文可读宽度放置，Word渲染后再验。
3. 架构箭头须区分UI请求、服务调用、数据流入和结果返回；历史预测CSV仅连接research展示路径，不能代替实际模型推理。
4. 互动教学保持简短；保留真实数据、专家评分与“未开展学习效果研究”的限制。
5. 本分工未完成V2最终Word逐页检查；不得以本图像检查代替全文渲染验收。
