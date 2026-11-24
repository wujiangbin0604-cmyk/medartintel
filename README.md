# ECG-AI · MIT-BIH 心电教学与人工智能实验平台

包含 ECG 波形浏览、六个已训练模型的心拍分类、科研结果与图集、Heartbeat Hunter 心电互动游戏，以及完整的实验源码和课程论文资料。前端为 React/Umi，后端为 FastAPI/PyTorch。

## 当前交付 V6与Linux部署修复 · 2026年11月21日

当前完整论文为 [V6 Word](paper/final/ECG_AI_课程论文_完整研究版V6.docx)及[同版PDF](paper/final/ECG_AI_课程论文_完整研究版V6.pdf)，共50页、26幅图、25张表，整合60次节律融合训练及独立校准拒识分析。V5与历史实验保留，正文、数据核验和评分说明见 [V6交付索引](PAPER_V6.md)。

本次修复Windows注册表路径在Linux下无法读取的问题，覆盖镜像构建校验、真实单拍推理和离线结果读取；新注册表统一保存正斜杠。模型权重、患者分区及实验指标保持原值。已有V6服务器可直接上传[独立修复脚本](deploy/ubuntu22/ecg_v6_linux_fix.py)，按[Linux修复与重建说明](SERVER_LINUX_FIX.md)执行。修正后的完整运行包名为 `ECG-AI_Full_Server_V6_LinuxFix_20261121.zip`。

从GitHub下载代码后，按下文的Windows、Linux或Docker流程启动；网页使用随仓库提供的数据和模型。服务器部署步骤见[更新说明](SERVER_UPDATE.md)。

2026年11月24日补充Windows首次安装修复：下载目录较深时，启动器自动选择较短的隔离环境目录，避免PyTorch安装触发Windows路径长度限制；也可用 `-VenvPath` 指定短目录。[本地运行说明](DEPLOY_LOCAL.md)包含Download ZIP与启动、自检步骤。

## 节律融合与可靠性实验室 · 2026年11月19日发布

新增 `/rhythm-lab`、历史 RR 特征及掩码、双分支模型、四模型消融和独立校准患者的拒识分析；Heartbeat Hunter 在专家答案后可跳转到同一真实心拍。原六模型、论文与历史实验保持独立。

在37个开发患者组、86,286拍上完成 **5折 × 3种子 × 4模型＝60组训练**。开发池分组交叉验证的合并OOF Macro-F1种子均值为：CNN 0.3584、RR-only 0.3754、融合0.4628、打乱RR 0.3530。S类Precision改善伴随平均Recall下降，F类识别仍较弱；详见[研究报告](research_extensions/INNOVATION_REPORT.md)。

GitHub 下载包含前端构建、60 个正式研究 checkpoint、样本索引和全部运行所需 JSON。**打开网页或推理无需训练 NPZ、Node.js 或重新训练**。Windows 运行 `powershell -ExecutionPolicy Bypass -File .\start-local.ps1`，随后访问 `http://127.0.0.1:8000/rhythm-lab`。

现有服务器更新（兼容旧ZIP部署）：[复制更新命令](SERVER_UPDATE.md)。首次/本地部署：[DEPLOY_LOCAL.md](DEPLOY_LOCAL.md)。执行服务器更新命令即可部署新页面。

## V5论文与独立复核 · 2026年11月19日

保留 [V5论文DOCX](paper/final/ECG_AI_课程论文_自然表达版V5.docx)及[同版PDF](paper/final/ECG_AI_课程论文_自然表达版V5.pdf)，[Markdown源稿](paper/draft/ECG_AI_课程论文_自然表达版V5.md)一并发布。该轮使用humanizer-zh调整29段中文表达，沿用既有实验数字、引文、图表、公式、英文摘要及结论。V5共39页，42条正文目录页码已核对；V1—V4保留，当前完整研究版为上文V6，详见[论文说明](paper/README.md)。

研究扩展本次复核了既有60个checkpoint的完整外层/校准预测及86,286行RR特征，另执行四模型训练Smoke Test、拒识复算和13对PNG/SVG重绘。Python回归96项、浏览器回归15项通过，前端构建及类型检查通过，见[本次复核交付](research_extensions/REVALIDATION_DELIVERY.md)。

## 最终优化与验收（2026年11月17日）

该阶段更新包含稳定性审计、12组受控实验、模型归因、报告导出、验收记录及V3论文。发布核对记录见[仓库同步记录](reports/repository_sync.md)。该阶段公开演示采用原有六模型版本。

- [最终验收与提交状态](FINAL_REVIEW.md)、[提交检查清单](SUBMISSION_CHECKLIST.md)。该阶段论文及后续V4润色版保留，当前论文见[V6交付索引](PAPER_V6.md)。
- [模型与数据划分审计](reports/cnn_generalization_audit.md)：全量原始信号重建、患者独立划分、索引、归一化与旧检查点重推通过。N/V验证/测试Macro-F1为0.6630/0.9865，患者109误报集中。
- [受控实验](reports/imbalance_experiments.md)：四方案、三随机种子，保留所有结果。验证预选RR方案在已查看测试集上的探索性复用结果为：Macro-F1 **0.5002±0.0036**，Balanced Accuracy **0.6056±0.0169**。S召回改善伴随大量误报；F召回约0.0108，低于新加权CE基线。
- 新增真实模型Integrated Gradients及完整性误差记录；教学界面仍使用原六模型，新研究候选与生产工件分开。
- 分析工作台可导出真实心拍、专家标注、三模型分数及工件/输入来源哈希。健康检查在六模型未全部就绪时返回503。
- 当前原58项及新增测试合计 **73项通过**，类型检查和生产构建通过；Chrome完成本机11项流程检查。公网通过直连验证波形、真实推理和三模型比较；配置网络出口返回502的差异见[演示验收报告](reports/application_demo_check.md)。

科学复验与复跑命令（先按下文构建训练NPZ；复跑始终使用新目录）：

```powershell
# 审计默认交付目录已存在，复跑时另设输出目录
.\.venv\Scripts\python.exe -m src.evaluation.stability_audit --output results/stability_audit_reproduction
# 原始审计门控证据随项目保存；新训练不覆盖12组交付实验
.\.venv\Scripts\python.exe -m src.evaluation.reproduce_controlled --output results/controlled_reproduction --stage train
# train完成并锁定后，才运行一次final；已执行过的目录会拒绝重复评估
.\.venv\Scripts\python.exe -m src.evaluation.reproduce_controlled --output results/controlled_reproduction --stage final
# 阅读/重建已交付实验的汇总，不进行新的训练或测试推理
.\.venv\Scripts\python.exe -m src.evaluation.controlled_report
```

训练协议与代码、数据哈希保存于 `results/controlled_imbalance_20261116/protocol.json`；逐seed检查点、历史和逐拍预测均在独立的 `runs/` 子目录。标准差按三个训练种子计算，描述训练随机性。

- **线上体验**：[打开 ECG-AI 工作台](http://47.83.150.55:8000/dashboard)
- **GitHub 仓库**：[wujiangbin0604-cmyk/medartintel](https://github.com/wujiangbin0604-cmyk/medartintel)
- **本地部署**：[Windows / Linux / Docker 完整说明](DEPLOY_LOCAL.md)
- **云服务器部署**：[Ubuntu 22.04 部署说明](deploy/ubuntu22/README_UBUNTU_22.04.md)

## 从 GitHub 下载并本地运行

```bash
git clone https://github.com/wujiangbin0604-cmyk/medartintel.git
cd medartintel
```

Windows 安装 **Python 3.12** 后，在 PowerShell 执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\start-local.ps1
```

Linux（Python 3.12）执行 `bash start-local.sh`。首次自动建立虚拟环境并安装固定的 CPU 推理依赖，以后使用本地环境启动。无需重新训练模型，也无需安装 Node.js。页面打开 [http://127.0.0.1:8000/dashboard](http://127.0.0.1:8000/dashboard)，按 Ctrl+C 停止。

已有 Docker Desktop（Linux containers）或 Docker Engine + Compose 时，也可在项目根目录执行：

```bash
docker compose up -d --build --wait --wait-timeout 240
```

仓库随附前端构建、48 条 MIT-BIH 原始记录、六个正式模型及网页需要的结果文件；不上传虚拟环境、node_modules、个人游戏记录或可重新生成的大型训练 NPZ/metadata.csv。需要训练时按下面的研究流程从原始数据重建。科研阶段记录保留在后文，其中早期阶段的范围只描述当时工作。

## 研究流程与阶段记录

项目按阶段包含全库数据探索、可复现的信号预处理与受试者独立分类基线。第一阶段只分析记录 100、200；第二阶段建立 48 条记录的预处理审计数据；第三阶段另用排除起搏记录后的 44 条数据完成 N/V 和 N/S/V/F 基线实验。原始 WFDB 文件保持不变。

## 第二阶段：预处理与受试者独立数据集

第二阶段使用官方 **全部48条记录**，完成N/V数据文件构建。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# 原始数据不完整时先补齐（官方 S3 镜像，官方 SHA256 核验，已有原始文件不覆盖）
.\.venv\Scripts\python.exe -m src.download --records all --mirror s3 --workers 4
# 完全离线构建/复跑全部记录
.\.venv\Scripts\python.exe -m src.preprocess --offline
```

成果位于 `data/processed/nv_v1/`：

| 文件 | 用途 |
| --- | --- |
| `train.npz`、`val.npz`、`test.npz` | 归一化单导联数组及逐样本来源 |
| `metadata.csv` | 全部原始标注，包括未入训练数据的类别与被排除窗口；`npz_row` 指向对应文件行号 |
| `split_manifest.csv`、`split_plan.json` | 全部记录的受试者及锁定分区，201/202 共享一组 |
| `processing_config.json` | 原始标签映射、滤波 SOS 系数、窗口及质量规则、种子和防泄漏政策 |
| `normalization.json` | 仅训练集拟合的均值/标准差、训练样本 ID 哈希及来源清单 |
| `training_class_weights.json` | 仅按训练标签计算的可选类权重，尚未应用 |
| `verification.json` | 数组/元数据/原标注一致、数据有限、受试者无交集等校验 |

查看 [预处理报告](reports/preprocessing_report.md)；图位于 `figures/preprocessing/`；全库原始标签计数、形态变化审计、排除计数和完整性信息位于 `results/preprocessing/`。

处理流程：实际 MLII 优先，否则首导联；先对连续有限信号执行 0.5–40 Hz Butterworth SOS 双向滤波，再用专家标注前 0.3 s、后 0.4 s 的**含端点 253 点窗口**截取。记录两端和非有限缺口两侧设 5 s 滤波保护区。边界/非有限/平直/重复目标位置等技术问题被明确记录；幅值大、ADC 触轨和形态变化只作保留样本的复核标记，不按外观改标签。

N←N/L/R/e/j，V←V/E，默认编码N=0、V=1；其余类别保留原始文件与元数据。100、200已用于前期探索，固定放入训练集；其余按受试者与预声明的V类覆盖条件一次性分层划分，受试者比例约70/15/15。201/202放在同一集合。分区和随机种子在滤波比较前写入并锁定；候选滤波比较使用训练记录，保留原始类别采样分布。

`X` 形状为 `(样本数, 1, 253)`，float32；`X_filtered` 为对应的滤波后 mV 信号；`y` 为 int64。所有分区使用同一个训练集标量均值/标准差，未逐拍缩放或按测试范围裁剪。加载示例：

```python
from pathlib import Path
import numpy as np

dataset_dir = Path('data/processed/nv_v1')
with np.load(dataset_dir / 'train.npz', allow_pickle=False) as data:
    X, y = data['X'], data['y']
    record_ids = data['record_id']
    original_positions = data['annotation_sample']
```

未来多分类可在新版本目录复用同一受试者分区：

```powershell
.\.venv\Scripts\python.exe -m src.preprocess --offline --classes N S V F --output-dir data/processed/nsvf_v1 --split-plan data/processed/nv_v1/split_plan.json
```

原始 `.dat/.hea/.atr` 保留，N组按N/L/R/e/j映射，V组按V/E映射。数据集采用依赖前后采样的双向滤波，面向离线分析；实时任务采用因果滤波。质量问题、导联差异、稀有类与患者差异在训练/验证侧处理，测试集按固定分区管理。

## 第三阶段：44 条记录基线分类实验

在保留上述 48 条全库审计与预处理产物的基础上，分类实验另建**排除 102、104、107、217 的 44 条非起搏记录版本**。PhysioNet 目录说明这四条记录含起搏心拍，原始模拟记录对常见起搏器伪迹识别方式保真不足；原始文件仍完整保留。新实验的滤波窗口与归一化在 44 条记录上独立重做，避免把被排除记录的信号用于当前模型。

```powershell
# 建 N/V 数据集；生成 44 条记录的锁定患者划分与全库/44条标签计数
.\.venv\Scripts\python.exe -m src.datasets.build --classes N V --output-dir data/processed/mitdb44_nv_v1 --offline

# 必须先通过小规模烟雾运行，再训练完整 N/V 基线
.\.venv\Scripts\python.exe -m src.classify --task nv --smoke-test
.\.venv\Scripts\python.exe -m src.classify --task nv

# 只有 N/V 正式训练、验证、预测与指标复核完成后才允许继续
.\.venv\Scripts\python.exe -m src.datasets.build --classes N S V F --output-dir data/processed/mitdb44_nsvf_v1 --split-plan data/processed/mitdb44_nv_v1/split_plan.json --offline
.\.venv\Scripts\python.exe -m src.classify --task nsvf --smoke-test
.\.venv\Scripts\python.exe -m src.classify --task nsvf
```

44 条实验以患者组为单位，按约 70/15/15 的目标比例得到 31/6/6 个 train/validation/test 患者组，对应 32/6/6 条记录；100、200 因前期已经查看而预先只放训练集。记录 201、202 合并成一个受试者组。稀有类在留出患者的覆盖有限，特别是四分类 S/F 需要结合实际 support、各类 Recall、Macro-F1 和混淆矩阵解释。模型配置位于 `configs/`；模型及日志分别保存在 `checkpoints/`、`results/classification/`。实验总报告为 `reports/classification/experiment_summary.md`；预处理与分类图分别位于 `figures/07_preprocessing/`、`figures/08_binary_classification/`、`figures/09_multiclass_classification/`。

`requirements.txt` 记录跨环境的兼容版本范围；`requirements-lock.txt` 记录已验证环境的精确包版本（Python 3.12.10、Windows、CPU-only PyTorch）。本地启动与保存模型加载使用Python 3.12。

基线模型包括Logistic Regression、Random Forest与1D-CNN。CNN使用加权CrossEntropyLoss与验证集Macro-F1早停，类别权重从训练集计算。三个模型完成拟合、保存检查点后统一评估一次测试集；代码从测试预测CSV重算指标，并输出CNN的类别分数与概率。

## 四分类失败诊断（新增）

对已完成的N/S/V/F四分类进行患者类别覆盖、患者级测试错误回顾、CNN权重策略train/validation对照和五折受试者分组CV。默认命令在train/validation上重新运行权重对照与CV；历史测试预测用于分患者统计和典型错误波形。原验证集已参与早停，交叉验证按探索性分析报告。

```powershell
.\.venv\Scripts\python.exe -m src.evaluation.four_class_diagnosis
# 如果只需重建报告和图，复用已保存的训练/交叉验证结果：
.\.venv\Scripts\python.exe -m src.evaluation.four_class_diagnosis --skip-weights --skip-cv
```

查看 [四分类失败诊断报告](reports/classification/four_class_failure_diagnosis.md)；统计表、患者级指标、OOF 预测、权重策略日志和完整性核验位于 `results/classification/nsvf44_v1/diagnosis/`；诊断图位于 `figures/11_four_class_diagnosis/`。

## 最终实验结果核验与课程报告（新增）

读取已保存的N/V与N/S/V/F测试预测，复算指标、核验split统计，生成整合报告和错误示例。该步骤使用此前已查看的测试预测。

```powershell
.\.venv\Scripts\python.exe -m src.evaluation.final_report
```

完整报告、核验记录、图表索引和项目完成情况位于 `reports/final/`。结果复算表位于 `results/classification/final_*`；新增报告图片位于 `figures/12_final_report/`。

## A–F 可视化图集（新增）

新版入口生成分布、原始波形、单心拍形态、节律、质量、PCA/t-SNE六类图集，并为**本轮每张图**自动写出用途、计算结果、分析说明和数据范围。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src.visualize --records 100 200 --offline
```

阅读 [逐图可视化报告](reports/visualization_summary.md)。本轮新图统一在 `figures/A_distribution/`、`B_waveforms/`、`C_morphology/`、`D_rhythm/`、`E_quality/`、`F_embedding/`，均为 300 dpi PNG。统计与追溯表独立放在 `results/visualization/`；`figure_catalog.csv` 是本轮全部图的唯一清单，`verification.json` 是完整性检查结果。此前第一阶段报告和输出继续保留。

```powershell
# 固定随机种子与 t-SNE 参数，完全离线重跑
.\.venv\Scripts\python.exe -m src.visualize --records 100 200 --offline --seed 20261027 --perplexities 15 40

# 扩展至全库；需联网下载尚未存在的原始文件
.\.venv\Scripts\python.exe -m src.visualize --records all

# 调整探索性降维的抽样计算量
.\.venv\Scripts\python.exe -m src.visualize --records 100 200 --offline --embedding-per-stratum 500 --embedding-max 3000
```

模块组织：加载复用 `src/io.py`，映射复用 `src/labels.py`，片段截取与描述量为 `src/heartbeat.py`；六类绘图位于 `src/visuals/`；报告生成为 `src/visualization_report.py`；主入口为 `src/visualize.py`。

随机20拍采用固定种子、不放回抽取；不足20拍时全取，缺失类别标记为缺失。`plotted_heartbeat_windows.csv` 保存叠图/网格所选每拍的记录、导联、原始样本和时间。网格以距类均值最近及不同峰峰值排序位置选例，波形取自原始信号。

形态与降维按同一导联名称独立处理；窗口默认前0.25 s、后0.45 s。`heartbeat_features.csv` 含有效窗口的峰峰值、最大/最小值、`sum(x²)/fs` 物理能量和减中位数后的能量。`all_beat_metadata.csv` 保留未能提取窗口的心拍、边界原因及完整RR；RR按记录内相邻心拍计算。图中的非N比例按 `(S+V+F+Q)/已映射心拍` 统计。

PCA对全部有效同导联窗口投影；t-SNE按记录×类别各最多500拍，再在总数超过3000时按层均衡分配，保留小样本层，不放回抽取。降维前比较“各窗减中位数”和“再除以各窗RMS”两个版本；t-SNE预先PCA到最多50维。相同投影分别按类别、记录着色，并比较perplexity=15/40。精确点坐标、原始标签、参数与解释率分别保存在 `embedding_coordinates.csv`、`embedding_parameters.csv`、`pca_explained_variance.csv`。投影分离和KL数值用于描述无监督降维结果。小数据运行时，perplexity必须小于抽样窗口数。

质量图中的1 s块中位数用于观察基线/幅值漂移，也受宽心拍和突变伪迹影响。0.5 mV阈值用于选择示意片段，样本保留。报告的视觉核查按原始数据哈希和运行配置匹配。

## 环境与安装

本版运行和保存模型加载需要64位Python 3.12，推荐Windows PowerShell。将项目放在当前用户有修改权限的目录。研究流程中下载两条记录约4 MB，需连接PhysioNet；全48条信号约94 MB（另加头文件和标注）。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m src --records 100 200
```

不需要激活虚拟环境，因此不受 PowerShell Activate.ps1 执行策略影响。Linux/macOS 对应使用 `.venv/bin/python`。`requirements.txt` 给出兼容范围；已验证环境的精确版本在 `requirements-lock.txt`，需要尽量复现本次环境时使用 `pip install -r requirements-lock.txt`。

## 重复运行与扩展

```powershell
# 本地原始文件与官方校验清单齐全后，完全离线重跑
.\.venv\Scripts\python.exe -m src --records 100 200 --offline

# 扩展至官方 RECORDS 清单中的全部 48 条记录
.\.venv\Scripts\python.exe -m src --records all

# 更换片段范围；按实际采样率取最近整数采样点
.\.venv\Scripts\python.exe -m src --records 100 200 --offline --pre-s 0.25 --post-s 0.45

# 独立输出目录；已下载原始数据需在该目录的 data/mitdb 中
.\.venv\Scripts\python.exe -m src --root E:\ecg_results --records 100 200

# 规则与窗口边界检查
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

默认项目根目录由代码位置确定。命令在项目根目录执行以找到 `src` 模块。已有 `.dat/.hea/.atr` 按哈希校验，校验不符时停止；获取新副本时另选输出目录。派生CSV、图和报告会被同名新结果替换。切换记录后，以本轮 `results/figure_manifest.csv` 为准，旧轮图片保留。`--records all` 逐条处理下载、绘图，内存中保留全库信号以汇总，建议至少4 GB可用内存。第一阶段实测记录为100、200。

## 目录

```text
data/mitdb/       官方 RECORDS、SHA256SUMS.txt、记录 .dat/.hea/.atr
data/processed/  历史全48条数据集；mitdb44_nv_v1 与 mitdb44_nsvf_v1 分类数据
src/             download.py/io.py/labels.py/analysis.py/visuals/visualize.py
src/preprocessing/ 连续滤波、心拍截取、训练集归一化、患者划分与审计
src/datasets/    44条数据构建、全48/44条标签统计与预处理绘图
src/models/      Logistic Regression、Random Forest、1D-CNN
src/training/    固定种子Smoke Test、正式训练、早停与日志
src/evaluation/  预测指标、混淆矩阵、误差图、报告和独立产物核验
configs/         binary_nv.json、multiclass_nsvf.json
checkpoints/     传统模型与CNN权重、Smoke Test和权重消融检查点
figures/         原67张探索图、07_preprocessing、08_binary_classification、09_multiclass_classification
results/         全库标签、划分、预测CSV、训练日志、指标JSON与final_verification.json
reports/         数据探索、可视化、预处理与classification/experiment_summary.md
tests/           标签、滤波、切片、患者划分、CNN形状和指标检查
requirements.txt / requirements-lock.txt
README.md
```

先阅读 [探索报告](reports/data_exploration.md)。重点结果如下：

| 文件 | 内容 |
| --- | --- |
| `results/raw_symbol_counts.csv` | 所有实际出现的原始 symbol 及数量，包含非心拍 |
| `results/label_mapping.csv` | 全部已知符号定义、中文、分组、数量、公开来源；0 次保留 |
| `results/aami_counts.csv` | 五组数量和占比，0 次类别保留；分母仅为已映射心拍 |
| `results/aami_counts_by_record.csv` | 分记录数量和记录内占比 |
| `results/annotations.csv` | 全部原始字段、样本编号、秒数及标注处导联幅值 |
| `results/annotations.jsonl` | 保留原始 aux_note 的 NUL 终止符，提供无损 JSONL 输出及往返验证 |
| `results/non_beat_annotations.csv` | 非心拍逐条记录，包括节律、质量与伪迹信息 |
| `results/unmapped_or_unknown_annotations.csv` | 映射规则以外心拍/未知项，不猜测类别 |
| `results/beats.csv` | 全心拍及窗口有效性、起止样本、相邻 RR、主导联窗口峰峰值 |
| `results/plotted_beats.csv` | 每个示例图中实际绘出的心拍及完整边界 |
| `results/signal_quality.csv` / `quality_windows.csv` | 全导联幅值、缺失、触轨、平直段与 10 秒质量代理 |
| `results/morphology_summary.csv` | 全部有效窗口的幅值范围及相邻 RR 描述统计 |
| `results/record_metadata.csv` | 采样率、导联、时长、头文件注释、对应验证 |
| `results/download_manifest.csv` | 官方来源 URL、字节数和 SHA256 核验 |
| `results/figure_manifest.csv` | 本轮全部图片及记录/导联/时间范围 |
| `results/verification.json` | 输出存在性、计数平衡、标注时间、窗口边界、原始数据未修改等验证 |

CSV 使用 UTF-8 BOM；若用 Excel 查看原始符号/aux_note，应按文本导入，保留 `+`、`=` 等字符串。部分原始 aux_note 含 NUL 终止符，普通 CSV 解析器可能截断；`aux_note_json` 可经 `json.loads` 无损还原，`aux_note_text` 仅去除尾部 NUL 方便显示，完整原始标注也保存为 `annotations.jsonl`。`sample` 从 0 开始；秒数为记录内相对时间；窗口 stop 列为 Python 切片的右开端点。

## 标签和观察约束

标签映射为：N←N,L,R,e,j；S←A,a,J,S；V←V,E；F←F；Q←/,f,Q。`symbol` 与 `aami_group` 分列，大小写敏感。分组使用原始专家标注；`!` 和 `x` 按官方定义作为非心拍单独保存。

双导联原始幅值图与带标注图均用实际物理单位。类间对比优先MLII，缺少时使用首导联。片段以原始专家标注为中心，默认前0.25 s、后0.45 s，360 Hz时253点（含中心和末点）；越界窗口跳过绘图，保留计数。组内图左侧显示原始幅值，右侧显示减去窗口中位数后的幅值。峰峰值按整个固定窗口计算，窗口内可能包含邻拍。

质量指标包括幅值、差分和触轨情况，用于探索性分析，样本保留。报告分别呈现统计、视觉观察和可能解释。开发助手的视觉备注按原始文件哈希及窗口参数匹配，对应记录100/200的观察。

模型按患者独立划分，**201和202同属一位受试者**。

## 来源

- [MIT-BIH 官方数据库 1.0.0、许可与引用要求](https://physionet.org/content/mitdb/1.0.0/)
- [PhysioNet 原始标注符号定义](https://physionet.org/static/lightwave/doc/annotations.html)
- [官方记录目录及记录 100/200 说明](https://physionet.org/files/mitdb/1.0.0/mitdbdir/records.htm)
- [WFDB Python 官方读入接口](https://wfdb.readthedocs.io/en/latest/io.html)
- [de Chazal et al. 2004，AAMI 五组映射文献](https://doi.org/10.1109/TBME.2004.827359)

数据原作者：Moody GB, Mark RG. The impact of the MIT-BIH Arrhythmia Database. IEEE Eng Med Biol Mag. 2001;20(3):45–50. DOI: 10.1109/51.932724。使用数据发表成果时请遵循官方页面的许可与引用要求。

## 第二阶段：本地 ECG-AI 教学工作台

第二阶段Web/API实现在 `web/`：MIT-BIH记录浏览、专家标注心拍选择、已保存LR/RF/1D-CNN模型推理、同拍比较和历史片段回放。模型推理使用既有44条受试者分组记录及MLII；其他本地完整记录提供波形浏览。

安装/启动、API、模型验证和演示说明见 [`web/docs/phase2_testing.md`](web/docs/phase2_testing.md)、[`web/docs/phase2_api.md`](web/docs/phase2_api.md) 和 [`web/docs/phase2_demo_guide.md`](web/docs/phase2_demo_guide.md)。最终交付记录在 [`web/docs/phase2_final_report.md`](web/docs/phase2_final_report.md)。

## 第三阶段：科研平台与课程答辩

新增 `/dashboard`、`/experiments`、`/generalization`、`/gallery` 和 `/presentation-demo`，统一蓝白医学科研界面，保留 `/ai-detection` 的ECG、三模型推理和历史回放。研究页面读取已核验的指标与图像。

推荐课堂演示采用本地生产构建：

```powershell
npm --prefix web/frontend run build
.venv\Scripts\python.exe -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8002
```

打开 `http://127.0.0.1:8002/presentation-demo`。完整过程、截图、实测性能与依赖情况见 [第三阶段交付报告](web/docs/phase3_final_report.md) 和 [答辩指南](web/docs/phase3_demo_guide.md)。

## 第四阶段：浅色医学科技风与交互动画

全站采用白色顶栏和可收起侧栏，增加三级动画设置、系统减少动画支持、Dashboard 联动、真实心拍高亮、三模型动态概率、RAF 历史回放、错误案例跳转和图库键盘浏览。`/ai-inference` 提供单拍检测入口，既有 API 与正式模型结果保留。

启动方式沿用上述生产命令，首页为 `http://127.0.0.1:8002/dashboard`。交付与实际验证见 [第四阶段交付报告](web/docs/phase4_final_report.md)、[动画设计](web/docs/phase4_animation_design.md)、[交互矩阵](web/docs/phase4_interaction_matrix.md)、[性能测量](web/docs/phase4_performance.md) 和 [视觉审查与截图](web/docs/phase4_visual_review.md)。

## 第五阶段：基于设计稿的视觉还原

参考包保存在 `web/design/reference/`。Dashboard 改为四 KPI 与三列分析区，ECG 工作台采用控制/主波形/节拍详情三列及独立回放栏，AI 检测采用单拍/推理结果分区与横向三模型卡。窄屏菜单提供 Tooltip 与完整名称展开，图表增加真实数量、百分比和对数视图。

启动方式不变。五尺寸修改前后截图、设计稿并排对照和实际测试结果见 [第五阶段交付](web/docs/visual_fidelity/final_report.md) 与 [视觉对照](web/docs/visual_fidelity/visual_comparison.md)。
