"""Build the explicitly authorized V3 revision from immutable V2 and real results.

The default command only checks inputs.  --build-draft writes a new Markdown
file and an exact operation log.  --build-docx formats that V3 source; PDF and
Word field refresh are deliberately separate operations owned by the caller.
Run with the bundled workspace Python, not the research virtual environment.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / "paper"
V2 = PAPER / "draft/ECG_AI_课程论文_修订版V2.md"
V2_DOCX = PAPER / "final/ECG_AI_课程论文_修订版V2.docx"
V3 = PAPER / "draft/ECG_AI_课程论文_最终优化版V3.md"
DOCX = PAPER / "final/ECG_AI_课程论文_最终优化版V3.docx"
QA = PAPER / "qa/v3"
RESULTS = ROOT / "results/controlled_imbalance_20261116"
V2_SHA = "136d7048b9cb090e22648e30c403ad9fdf5e482d2ece7150108b7ceac1bfeac0"
TITLE = "心拍分类与可视化系统设计"
SUBTITLE = "基于一维卷积网络的患者独立评估"
EN_TITLE = "Heartbeat Classification and Visualization System"
EN_SUBTITLE = "Patient-independent Evaluation of One-dimensional Convolutional Networks"
OFFICIAL = "https://xjzz.fzu.edu.cn/info/1083/3979.htm"
CLASSES = ["N", "S", "V", "F"]
VARIANTS = ["ce_inverse", "ce_sqrt", "focal_sqrt", "focal_sqrt_rr"]
LABELS = {"ce_inverse": "逆频率CE", "ce_sqrt": "平方根CE",
          "focal_sqrt": "平方根Focal", "focal_sqrt_rr": "平方根Focal＋RR分支"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def ms(row: dict, metric: str) -> str:
    return f"{float(row[metric + '_mean']):.4f}±{float(row[metric + '_sample_sd']):.4f}"


def f(row: dict, metric: str) -> float:
    return float(row[metric + "_mean"])


def load_inputs(release_path: Path) -> dict:
    require(sha(V2) == V2_SHA, "V2 source changed; inspect before constructing a revision")
    final = read_json(RESULTS / "test_evaluation.json")
    locked = read_json(RESULTS / "selection_locked.json")
    protocol = read_json(RESULTS / "protocol.json")
    require(final.get("status") == "completed", "Final frozen test phase has not completed")
    require(final["selection_sha256"] == sha(RESULTS / "selection_locked.json"), "Selection hash changed")
    require(locked["protocol_sha256"] == sha(RESULTS / "protocol.json"), "Protocol hash changed")
    require(final["selected_before_test"] == locked["selected_variant"], "Selected variant changed after test")
    require(final["runs"] == 12, "All twelve predeclared runs are required")
    aggregate = rows(RESULTS / "controlled_aggregate_summary.csv")
    classes = rows(RESULTS / "controlled_class_summary.csv")
    ablation = rows(RESULTS / "controlled_ablation_summary.csv")
    require(len(aggregate) == 8, "Four variants and two partitions must be summarized")
    for variant in VARIANTS:
        for split in ("val", "test"):
            row = next(r for r in aggregate if r["variant"] == variant and r["split"] == split)
            require(int(row["seeds"]) == 3, "Every aggregate must retain all three seeds")
    explanation = read_json(RESULTS / "explanations/manifest.json")
    release = read_json(release_path)
    require(bool(release.get("verification_complete")), "Caller must supply completed, actual software verification")
    require(bool(release.get("verification_rows")), "Actual verification evidence is required")
    for name in ("controlled_overall.png", "controlled_minority_tradeoffs.png",
                 "controlled_paired_ablation.png", "integrated_gradients.png"):
        require((ROOT / "figures/final_optimization" / name).is_file(), "Required scientific figure is absent: " + name)
    return {"final": final, "locked": locked, "protocol": protocol, "aggregate": aggregate,
            "classes": classes, "ablation": ablation, "explanation": explanation,
            "release": release, "release_path": release_path}


def table(caption: str, headers: list[str], values: list[list[Any]]) -> str:
    return "\n".join([caption, "", "| " + " | ".join(headers) + " |",
                       "|" + "|".join("---" for _ in headers) + "|",
                       *["| " + " | ".join(str(v) for v in row) + " |" for row in values]])


def controlled_text(inputs: dict) -> tuple[str, str, str]:
    agg = {(r["variant"], r["split"]): r for r in inputs["aggregate"]}
    selected = inputs["locked"]["selected_variant"]
    val, test = agg[selected, "val"], agg[selected, "test"]
    base = agg["ce_inverse", "test"]
    setup = """## 3.5 类别不平衡与RR上下文方案

在保留原始CNN及六个生产工件的基础上，增加四分类受控实验。四个预声明方案依次为逆频率加权交叉熵（ce_inverse）、平方根平滑加权交叉熵（ce_sqrt）、平方根加权Focal Loss（focal_sqrt）和增加过去RR上下文分支的Focal方案（focal_sqrt_rr）。Focal Loss通过对易分类样本施加较小调制权重，改变损失贡献[13]；本实验取γ=2，先对每拍的负对数概率乘以类别权重α和调制项(1−p)的γ次幂，再以批内α之和归一化。γ=0时退化为同α的加权交叉熵，因此对照中的损失均值口径一致。α为训练侧逆频率权重的平方根，全局乘常数不改变该加权均值。方法的价值由完整逐类结果检验，不因名称而预设优于基线。

RR方案保留原三层波形编码器，将四维时间特征经4→16的ReLU分支，与64维波形表示拼接，再由80→4线性层分类。该方案比原结构增加144个参数。特征包括上一RR间期、过去最多十个RR间期均值、上一RR与该均值之比、上一RR与再前一RR之比；均由过去专家心拍位置计算，不使用类别标签、下一RR、患者编号或记录编号作为输入。附加StandardScaler仅以训练样本拟合。记录开始缺少历史间隔时按协议使用0.8 s默认值。RR方案同时增加时间信息和可训练分支，因此比较评价的是这一组合，不能把差异完全归因于单个特征。

四个方案均使用原患者分区、253点波形、标签与训练侧标量归一化。三个随机种子为20261027、20261116和20261117，训练上限25轮，早停耐心值5，学习率0.001，批大小256。每次训练依据验证集四类Macro-F1选择检查点；之后按三个种子的平均验证Macro-F1选定方案，完全同分按预声明配置顺序处理，不挑选最好种子。所有检查点及选型结果冻结后，才进入一次最终测试评估阶段。原测试集此前已经查看，故这一阶段属于旧测试集的探索性复用，不是新的盲测或外部患者验证。
"""
    values = []
    for variant in VARIANTS:
        for split in ("val", "test"):
            r = agg[variant, split]
            values.append([LABELS[variant], "验证" if split == "val" else "旧测试",
                           ms(r, "accuracy"), ms(r, "macro_f1"), ms(r, "balanced_accuracy")])
    overall = table("表16 新训练四方案的三种子总体结果", ["方案", "分区", "Accuracy", "Macro-F1", "Balanced Accuracy"], values)
    minority = table("表17 新训练方案的测试侧逐类结果", ["方案", "S Recall / F1", "F Recall / F1", "V Recall / F1"], [
        [LABELS[v], ms(agg[v, "test"], "S_recall") + " / " + ms(agg[v, "test"], "S_f1"),
         ms(agg[v, "test"], "F_recall") + " / " + ms(agg[v, "test"], "F_f1"),
         ms(agg[v, "test"], "V_recall") + " / " + ms(agg[v, "test"], "V_f1")] for v in VARIANTS])
    result = f"""## 5.8 多种子受控改进实验

新增12组训练均按3.5节预声明方案完成。Balanced Accuracy定义为四个固定类别Recall的等权均值；表中均值及样本标准差由三个随机种子计算，既不是患者间标准差，也不是置信区间。原表8—表13保留历史实验口径，新增ce_inverse是同方法多种子重训，不能与历史单次训练混写为同一结果。

{overall}

![图17 四方案在验证与旧测试分区的总体表现](../../figures/final_optimization/controlled_overall.png)

验证均值预先选定的方案为{LABELS[selected]}（{selected}），其验证Macro-F1为{ms(val, 'macro_f1')}，旧测试Macro-F1为{ms(test, 'macro_f1')}。相对本轮逆频率CE基线，旧测试Macro-F1均值变化为{f(test, 'macro_f1') - f(base, 'macro_f1'):+.4f}，Accuracy变化为{f(test, 'accuracy') - f(base, 'accuracy'):+.4f}。此处报告验证选型后的观察，不依据测试表重排优胜方案，也不将新方案直接替换到生产模型注册表。

{minority}

![图18 少数类召回与F1的实际取舍](../../figures/final_optimization/controlled_minority_tradeoffs.png)

所选方案在旧测试侧S类Precision、Recall、F1均值分别为{f(test, 'S_precision'):.4f}、{f(test, 'S_recall'):.4f}、{f(test, 'S_f1'):.4f}，F类分别为{f(test, 'F_precision'):.4f}、{f(test, 'F_recall'):.4f}、{f(test, 'F_f1'):.4f}，V类Recall与F1为{f(test, 'V_recall'):.4f}和{f(test, 'V_f1'):.4f}。召回上升与误报增加可以同时发生，因此这些结果须与总体Accuracy和逐类Precision共同解释。三个种子仍共享相同心拍和六个测试患者，不等于三批独立患者证据。

与新训练逆频率CE相比，所选方案的S类F1从{f(base, 'S_f1'):.4f}升至{f(test, 'S_f1'):.4f}，但F类Recall从{f(base, 'F_recall'):.4f}降至{f(test, 'F_recall'):.4f}，F1从{f(base, 'F_f1'):.4f}降至{f(test, 'F_f1'):.4f}。因此本轮没有实现S与F同时改善；F类Precision较高仍伴随大部分真实F被漏分。新增策略的实际收益主要体现在S、V和总体指标的组合变化，不能宣称已解决融合心拍识别。相对于仅改变Focal调制的方案，RR分支组合在本分区的整体表现较好，仍需与其额外参数和患者来源一同解释。

相邻方案分别比较权重平滑、Focal调制及RR分支组合，图19以相同种子的成对差值展示变化；负值同样保留。前两组在波形结构不变时更接近损失因素对照，RR组则同时改变输入信息和参数量。研究问题是这些改动如何影响少数类识别与误报，而非通过大量方案搜索最高测试分数。

![图19 相邻受控方案的成对种子变化](../../figures/final_optimization/controlled_paired_ablation.png)

本轮没有删除困难患者或修改S/F标签。验证S高度集中于患者232，旧测试S仅10拍、来自3个患者，F的371拍中370拍来自患者208；损失函数与RR上下文均不能增加独立形态来源。即使某项均值上升，患者组成的限制仍然存在。新增对照支持比较当前固定条件下的训练策略，不能据此认定已经解决少数类的临床泛化问题。
"""
    manifest = inputs["explanation"]
    require(manifest.get("test_used_for_explanations") is False, "Explainability examples must not be test-selected")
    examples = manifest["examples"]
    absolute_error = max(float(e["completeness_absolute_error"]) for e in examples)
    relative_error = max(float(e["completeness_relative_error"]) for e in examples)
    explain = f"""## 5.9 真实模型的梯度归因分析

采用Integrated Gradients对真实CNN的预测类别logit进行输入归因[14]。该方法沿参考输入到实际输入的路径累计梯度；本项目以归一化波形零输入和标准化RR零输入作为参考，分别对应训练均值，并非生理正常心拍模板。使用验证选定方案{manifest['variant']}，从三个种子中取验证排序居中的{manifest['seed']}，再取验证集每个真实类别的中间位置样本，共{len(examples)}例，不按测试表现筛选。图20的波形及波形/RR归因均来自实际前向与梯度计算，样本来源、目标类别与检查点哈希由清单记录。

![图20 真实心拍及模型的Integrated Gradients归因](../../figures/final_optimization/integrated_gradients.png)

数值积分采用128步，并保存64步到128步的波形归因变化。四例的完整性最大绝对误差为{absolute_error:.6f}、最大相对误差为{relative_error:.6f}，用于检查近似积分的一致性，不是分类性能指标。归因值描述给定模型、参考输入和目标输出的局部数值关系，可能随参考基线和目标类别变化。某个时间区间贡献较大，不足以证明模型具有医学知识，也不等于该区间具备因果诊断意义。RR分支方案还包含波形以外的输入，单看波形归因不能解释全部决策。归因用于定位值得复核的区域，并补充定量错误分析；本研究没有以归因图片代替分类指标，也没有宣称模型经专家验证地识别了P波或QRS机制。
"""
    return setup, result, explain


class Revision:
    def __init__(self, source: str):
        self.text = source
        self.ops: list[dict] = []

    def replace(self, before: str, after: str, reason: str) -> None:
        require(self.text.count(before) == 1, "Revision anchor is missing/ambiguous: " + before[:70])
        self.text = self.text.replace(before, after, 1)
        self.ops.append({"reason": reason, "before": before, "after": after,
                         "before_sha256": hashlib.sha256(before.encode()).hexdigest(),
                         "after_sha256": hashlib.sha256(after.encode()).hexdigest()})

    def section(self, start: str, end: str, content: str, reason: str) -> None:
        before = self.text[self.text.index(start):self.text.index(end)]
        self.replace(before, content.rstrip() + "\n\n", reason)


def bibliography(text: str) -> tuple[str, dict]:
    body, ref_text = text.split("# 参考文献", 1)
    endmatter = ""
    if "# 附录" in ref_text:
        ref_text, endmatter = ref_text.split("# 附录", 1)
        endmatter = "# 附录" + endmatter
    refs = {int(n): value for n, value in re.findall(r"^\[(\d+)\]\s*(.+)$", ref_text, re.M)}
    refs[11] = "OLIVEIRA R F, MOREIRA G J P, FREITAS V L S, et al. Leveraging visibility graphs for enhanced arrhythmia classification with graph convolutional networks[EB/OL]. arXiv预印本, 2024[2026-11-16]. https://arxiv.org/abs/2404.15367v2."
    refs[12] = "CHEN M, LI Y, SHI W, et al. Attention-enhanced convolutional neural network for inter-patient classification of premature ventricular contraction from ECG[C]//Computing in Cardiology. 2024, 51. https://cinc.org/archives/2024/pdf/CinC2024-463.pdf."
    refs[13] = "LIN T Y, GOYAL P, GIRSHICK R, et al. Focal loss for dense object detection[EB/OL]. arXiv预印本, 2017[2026-11-16]. https://arxiv.org/abs/1708.02002."
    refs[14] = "SUNDARARAJAN M, TALY A, YAN Q. Axiomatic attribution for deep networks[C]//Proceedings of the 34th International Conference on Machine Learning. PMLR, 2017, 70: 3319-3328. https://proceedings.mlr.press/v70/sundararajan17a.html."
    pattern = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")
    order: list[int] = []
    def numbers(value: str) -> list[int]:
        out: list[int] = []
        for token in value.split(","):
            if "-" in token:
                a, b = map(int, token.split("-")); out.extend(range(a, b + 1))
            else:
                out.append(int(token))
        return out
    for hit in pattern.finditer(body):
        for number in numbers(hit[1]):
            require(number in refs, "Unknown citation " + str(number))
            if number not in order:
                order.append(number)
    mapping = {old: new for new, old in enumerate(order, 1)}
    def convert(hit: re.Match) -> str:
        mapped = [mapping[n] for n in numbers(hit[1])]
        if len(mapped) >= 3 and mapped == list(range(mapped[0], mapped[-1] + 1)):
            return f"[{mapped[0]}-{mapped[-1]}]"
        return "[" + ",".join(str(n) for n in mapped) + "]"
    body = pattern.sub(convert, body)
    return body.rstrip() + "\n\n# 参考文献\n\n" + "\n\n".join(
        f"[{mapping[old]}] {refs[old]}" for old in order) + "\n\n" + endmatter, mapping


def chapter_numbers(text: str) -> tuple[str, dict]:
    maps: dict[str, dict[str, str]] = {"图": {}, "表": {}, "公式": {}}
    chapter = 0; count = {"图": 0, "表": 0, "公式": 0}
    for line in text.splitlines():
        match = re.match(r"# 第([1-6])章", line)
        if match:
            chapter = int(match[1]); count = {"图": 0, "表": 0, "公式": 0}
        match = re.match(r"!\[图(\d+)\s", line)
        if match:
            count["图"] += 1; maps["图"][match[1]] = f"{chapter}-{count['图']}"
        match = re.match(r"表(\d+)\s", line)
        if match:
            count["表"] += 1; maps["表"][match[1]] = f"{chapter}-{count['表']}"
        if line.startswith("$$"):
            match = re.search(r"（(\d+)）", line)
            require(match is not None, "Equation has no identifier")
            count["公式"] += 1; maps["公式"][match[1]] = f"{chapter}-{count['公式']}"
    for prefix in ("图", "表"):
        text = re.sub(prefix + r"(\d+)(?![\d-])", lambda m: prefix + maps[prefix].get(m[1], m[1]), text)
    text = re.sub(r"（(\d+)）", lambda m: "（" + maps["公式"].get(m[1], m[1]) + "）", text)
    return text, maps


def build_draft(inputs: dict) -> str:
    source = V2.read_text(encoding="utf-8")
    revision = Revision(source)
    revision.replace(source.splitlines()[0], "# " + TITLE + "\n\n副标题：" + SUBTITLE, "缩短主标题并保留研究范围")
    agg = {(r["variant"], r["split"]): r for r in inputs["aggregate"]}
    selected = inputs["locked"]["selected_variant"]
    val, test = agg[selected, "val"], agg[selected, "test"]
    abstract = f"""## 摘要

针对心电图标注心拍分类与课程实验展示需求，本文基于MIT-BIH心律失常数据库，比较逻辑回归、随机森林和一维卷积神经网络，并实现ECG-AI可视化系统。实验排除四条含起搏心拍记录，将保留的44条记录归为43个患者组，以31、6、6个患者组划分训练、验证和测试分区。信号经固定带通滤波后，围绕专家位置截取253点窗口，归一化参数仅以训练数据拟合。原N/V二分类CNN测试Accuracy为0.9957、Macro-F1为0.9865，但验证Macro-F1为0.6630；重新推理、标签及数据对应检查支持原结果可复现，验证误报高度集中于患者109。原四分类随机森林和CNN的Macro-F1分别为0.4656和0.4460，较高总体准确率没有转化为可靠的S/F识别。

进一步保留固定患者分区，预声明逆频率交叉熵、平方根交叉熵、Focal Loss及增加过去RR分支的四个方案，各训练三个随机种子，按平均验证Macro-F1锁定{LABELS[selected]}，其验证与旧测试Macro-F1分别为{ms(val, 'macro_f1')}和{ms(test, 'macro_f1')}。验证与测试的患者组成不同，大量相关心拍不能代替独立患者证据；新增策略没有使S、F同时改善，指标上升与漏检退步均完整保留。旧测试集此前已查看，新增结果属于冻结协议后的探索性复用，不能视为独立盲测。真实模型的梯度归因用于补充错误分析，不证明医学因果机制。系统贯通真实波形、专家标注、三模型推理、历史回放、错误展示与教学互动，六个原生产模型保持独立保留。结果表明，训练策略应结合逐类误报、患者覆盖和随机性共同评价；本项目贡献主要是可复现实验、受控对照和教学系统整合，适用范围限于既有数据库中的专家标注心拍，不构成临床诊断有效性证据。

关键词：心电图，心拍分类，类别不平衡，患者独立评估，可视化系统

## Abstract

This study addresses the classification of annotated electrocardiographic heartbeats and the presentation of reproducible course experiments. Logistic regression, random forests and a one-dimensional convolutional neural network were compared using the MIT-BIH Arrhythmia Database, and their trained artifacts were integrated into the ECG-AI visualization system. Four recordings containing paced beats were excluded. The remaining 44 recordings represented 43 patient groups, which were assigned to training, validation and test partitions containing 31, six and six groups. Fixed band-pass filtering preceded extraction of 253-sample windows around expert annotations. Normalization statistics were fitted using training data only.

The original N/V convolutional model achieved a test accuracy of 0.9957 and a macro-F1 of 0.9865, whereas its validation macro-F1 was 0.6630. Replay and correspondence checks supported reproducibility of these outputs; most validation false positives originated from patient 109. For the original four-class task, random forests and the convolutional model obtained macro-F1 values of 0.4656 and 0.4460, respectively. High overall accuracy therefore coexisted with poor recognition of the S and F classes. A controlled extension retained the same patient split and compared inverse-frequency cross-entropy, square-root-weighted cross-entropy, focal loss and a focal model with past RR context. Three predeclared random seeds were retained for every configuration. The configuration {selected} was locked using mean validation macro-F1 before the final evaluation stage. Its validation and previously viewed test macro-F1 values were {ms(val, 'macro_f1')} and {ms(test, 'macro_f1')}, respectively, reported as mean and sample standard deviation across seeds. Patient composition differed between partitions, and correlated beats did not provide independent patient evidence. The selected extension did not improve both minority classes: improved S recognition coexisted with poorer F recall and F1 than the retrained inverse-frequency baseline. Reuse of an already inspected test set was treated as exploratory, rather than as a new blinded or external evaluation.

Integrated Gradients from actual model computations supplemented the error analysis without establishing clinical mechanisms. The application connects real waveforms, expert annotations, three-model inference, historical playback, error inspection and interactive teaching. The six original production artifacts were retained separately from the new experimental models. The findings emphasize that weighting, minority-class false positives, patient coverage and training randomness must be assessed together. The contribution is a reproducible comparison, a controlled training investigation and an integrated teaching system. The evidence applies to expert-centered beats in this database and does not establish clinical diagnostic effectiveness or reliable performance on arbitrary unannotated recordings.

Key words: electrocardiogram, heartbeat classification, class imbalance, patient-independent evaluation, visualization system

"""
    revision.section("## 摘要", "<!--TOC-->", abstract, "依据真实新增实验同步中英文摘要")
    old = "本文核对数据构建、标签映射、患者分组和预处理配置，从保存的逐拍预测重新计算六组测试指标；复核既有四分类诊断与五折结果，并整理真实错误波形；依据当前代码审计Web功能和部署一致性。图1给出了项目技术流程。模型比较、结果分析与系统集成构成主要课程成果，普通工程实现不作为算法创新主张。"
    new = "本项目完成患者分组数据集、三类模型比较和ECG-AI系统整合。实验以逐类指标和患者来源解释N/V与四分类的差异，增加三随机种子的损失与RR上下文受控对照，并用真实梯度归因补充错误复核。系统把波形、专家标签、保存模型与课堂互动贯通。图1概括数据与模型流程。这些工作属于实验设计、结果分析和教学工程贡献，不提出全新的网络算法。"
    revision.replace(old, new, "将主要工作改为成果表达，减少审计过程叙事")
    anchor = "## 1.3 研究目标"
    recent = "近年来，心拍分类研究继续探索更丰富的表示与跨患者评价。Oliveira等的图表示与图卷积工作仍指出类别不平衡及室上性心拍识别的困难[11]；该来源为公开预印本，不能据此建立跨论文性能名次。Chen等将注意力增强卷积用于跨患者室性早搏识别，并结合形态与间期信息[12]。这些研究提示节律上下文具有比较价值，但其标签、训练和评估条件与本文不同。本文仅据此设置过去RR输入对照，不声称复现其模型或性能。\n\n"
    revision.replace(anchor, recent + anchor, "补充已核实近期一手研究并限定可比性")
    setup, results, explanation = controlled_text(inputs)
    revision.replace("本文CNN输入为253点单心拍窗口，没有显式RR特征。", "原始比较中的CNN输入为253点单心拍窗口，没有显式RR特征；新增RR分支另作受控对照。", "区分原波形基线与新增RR研究模型")
    revision.replace("../figures/v2/fig01_workflow.png", "../figures/final_v3/fig01_workflow.png", "更新流程图以同时表示原工件复验与新增训练")
    revision.replace("# 第四章 实验设计与评价指标", setup + "\n# 第四章 实验设计与评价指标", "增加预声明受控方法与测试隔离政策")
    audit = read_json(ROOT / "results/stability_audit_20261116/nv_audit.json")
    overlap = audit.get("partition_overlap", {})
    require(overlap.get("same_record_cross_split_overlapping_intervals") == 0, "Unresolved overlapping-record window issue")
    require(all(not v for k, groups in overlap.items() if isinstance(groups, dict) for v in groups.values()), "Patient/record/sample overlap is unresolved")
    new_audit = "数据完整性复验核对全部样本编号、原符号、映射标签、采样位置、导联及数组行次；训练、验证和测试的患者、记录及样本编号集合互斥，同记录跨分区重叠窗口计数为0。滤波后mV窗口及归一化窗口的规范字节哈希均未发现跨分区精确重复。该检查不能穷举不同患者之间的近似形态，也不把形态相似直接当作同源泄漏。当前生产工件在eval模式下重新推理，支持原N/V验证与测试指标复现；没有通过修改分区、标签或剔除患者109来消除差异。历史CSV缺少检查点哈希，故仍不能完整重建最初的全部选择历史。\n\n"
    revision.replace("## 5.2 N/S/V/F四分类结果", new_audit + "## 5.2 N/S/V/F四分类结果", "用实际重推和全样本审计强化性能差异诊断")
    revision.replace("# 第六章 ECG-AI系统设计与实现", results + "\n" + explanation + "\n# 第六章 ECG-AI系统设计与实现", "加入12组受控实验、全指标取舍和真实IG分析")
    release = inputs["release"]
    verification_table = table("表14 系统功能与最终实际验证", ["检查项目", "实际结果", "证据"],
                               [[r["item"], r["result"], r["evidence"]] for r in release["verification_rows"]])
    system = "## 6.3 功能实现与验证\n\n" + release["verification_intro"] + "\n\n" + verification_table + "\n\n"
    system += "软件测试验证文件读取、接口行为与预期交互；模型对新患者的有效性仍需单独的统计与医学评价。前端构建成功和接口返回正常，不等于已经验证临床适用性。\n\n"
    screenshot = release.get("demo_screenshot")
    if screenshot:
        require((ROOT / screenshot).is_file(), "Real final demonstration screenshot is absent")
        system += f"![图21 最终课堂演示流程的真实页面](../../{screenshot.replace(chr(92), '/')})\n\n"
        system += release.get("demo_caption", "图中显示实际运行页面，模型输出与对应工件一致。") + "\n\n"
    revision.section("## 6.3 功能实现与验证", "## 6.4 模型部署一致性", system, "同步本轮真实验收结果与截图，不沿用历史通过数")
    if release.get("demo_flow_text"):
        revision.replace("# 第七章 总结与展望", "## 6.6 课堂演示与结果导出\n\n" + release["demo_flow_text"] + "\n\n# 第七章 总结与展望", "根据已验收功能说明完整演示与真实导出")
    # These are exact, small text edits; the historic tables/metrics remain intact.
    edits = [
        ("正式数据处理环境记录Python 3.12.10、NumPy 2.5.4、SciPy 1.18.1、WFDB 4.3.1和scikit-learn 1.9.1，项目依赖锁记录PyTorch 2.14.1。上述版本来源于保存的环境与依赖文件，不表示论文生成时重新完成了该环境的全部复现。项目在Windows环境组织和运行，正式训练配置明确使用CPU；现存证据不足以填写具体CPU或显卡型号。Web前端和后端依赖分别由各自配置维护，不与训练环境混写。", "原数据处理环境记录Python 3.12.10、NumPy 2.5.4、SciPy 1.18.1、WFDB 4.3.1、scikit-learn 1.9.1，依赖锁记录PyTorch 2.14.1。新增受控训练实际使用Python 3.12.10、NumPy 2.5.4与PyTorch 2.14.1+cpu，固定CPU线程数4。项目在Windows环境组织和运行；具体硬件型号未纳入已有实验记录，因此不补写。前后端依赖由各自配置维护，与训练环境分开记录。"),
        ("本文读取既有工件与预测，未重新训练，也没有根据本次错误分析重新选择正式模型。", "原始实验的检查点及预测独立保留；新增训练另按3.5节方案执行，不用错误案例重新选择原模型。"),
        ("固定测试虽在原训练后执行，本轮读取的是已有预测；回顾性查看不能恢复测试集未被触碰的状态。", "原始固定测试在训练后执行；新增重推和受控训练均记录其回顾性复用边界，不能恢复测试集未被触碰的状态。"),
        ("本轮没有用案例调整阈值、损失权重或检查点。", "错误案例仅用于描述性复核，没有用它们调整阈值或重新选择原检查点。"),
        ("图注：图14—图16均来自2026年11月4日保留的真实浏览器截图。本轮裁剪核心区域以放大文字，其中图15将三张结果卡片纵向重排；未重绘波形或改变预测值。它们是对应阶段已实现功能的证据，不称为本轮新运行截图。", "图14和图15来自2026年11月4日的真实浏览器页面，其中图15仅重排结果卡片便于阅读，未重绘波形或修改预测值；最终验收页面另在6.3节展示。"),
        ("本轮直接汇总已有部署对照CSV（phase3_validation），结果见表15。", "部署一致性对照来自phase3_validation保存记录，结果见表15。"),
        ("当前固定划分下，CNN在N/V任务中获得较好的按拍汇总结果，但扩展为四分类后，优势没有继续保持。", "线性模型、树集成与卷积网络对输入关系采用不同假设：逻辑回归在波形向量上建立线性边界，随机森林表达分段非线性关系，CNN共享局部时序卷积参数。当前固定划分下，CNN在N/V任务中获得较好的按拍汇总结果，但扩展为四分类后，优势没有继续保持。"),
    ]
    for before, after in edits:
        revision.replace(before, after, "定点改进最终论文的贡献与科学表达")
    conclusion = f"""# 结论

本项目围绕MIT-BIH单导联专家标注心拍，完成数据处理、模型对照、患者来源分析和ECG-AI教学系统整合。原患者独立N/V测试中，CNN的Accuracy为0.9957、Macro-F1为0.9865；验证Macro-F1仅0.6630的差异在重新推理后仍存在，且验证误报集中于患者109。数据与工件复核支持结果一致性，没有发现已检查范围内的跨分区同源窗口或精确波形重复；这不等于证明所有潜在泄漏与历史选择偏倚均不存在。四分类中随机森林总体指标较高，但S/F识别不足，说明总体准确率不能替代逐类能力判断。

新增四方案、三种子的受控实验保留全部分区和标签，并在最终测试阶段前锁定验证选型。选定{LABELS[selected]}的验证及旧测试Macro-F1分别为{ms(val, 'macro_f1')}和{ms(test, 'macro_f1')}。其逐类变化、整体误报和种子波动均完整报告，不以单个最好种子或召回率替代总体证据。过去RR分支和损失对照扩大了研究问题，真实梯度归因补充了错误观察；二者都不构成新医学机制的证明。系统贡献是将真实信号、专家标签、模型推理、错误反馈与教学互动贯通，生产六模型与探索性新模型分开保存。

研究仍受限于单一历史数据库、六个固定测试患者及S/F患者来源集中。三个随机种子反映训练随机性，不能增加独立患者证据；旧测试复用不是新的外部盲测。模型依赖专家位置、离线双向滤波，尚未完成自动定位误差、临床校准、前瞻性验证或教学效果用户研究。后续应在新增患者来源上预先冻结评估方案，单独评价自动R峰定位及节律上下文的贡献，再考虑模型部署与概率校准。现有成果适合课程实验和教学展示，不能输出临床诊断结论。

"""
    revision.section("# 第七章 总结与展望", "# 参考文献", conclusion, "结论不加章号，并同步新增实验及残余限制")
    endmatter = """
# 附录1 数据与复现说明

数据来源为公开的MIT-BIH Arrhythmia Database及其专家标注。项目在公开数据范围内开展算法与软件实验，没有新增受试者招募或临床干预；不据此虚构伦理审批编号。原始记录、训练配置、模型工件和逐拍预测的来源与哈希由仓库结果文件记录。原实验与新受控实验分目录保存，复现步骤见项目README和对应实验报告。

课程成果署名作者为吴江彬。AI工具用于辅助代码开发、资料整理、实验检查和论文修订；指标来自实际运行或保存预测复算，AI生成文本不作为独立实验结果。作者负责核查提交成果的数据、实现与结论。项目材料未列示专项资助或商业合作信息，本稿不据此补写未经确认的经费或利益关系。

# 致谢

感谢公开数据库和开源软件的维护者为课程实验提供数据与工具基础。相关数据、方法和软件的贡献按照实际来源标注，不将其列为本文原创算法。
"""
    revision.text = revision.text.rstrip() + "\n\n" + endmatter.lstrip()
    for cn, number in [("一", 1), ("二", 2), ("三", 3), ("四", 4), ("五", 5), ("六", 6)]:
        revision.text = revision.text.replace("# 第" + cn + "章", "# 第" + str(number) + "章")
    text, reference_mapping = bibliography(revision.text)
    text, number_mapping = chapter_numbers(text)
    # Removing a superseded screenshot from the old function table does not
    # remove its historic source file; all actual figures must still resolve.
    image_records = []
    for caption, target in re.findall(r"!\[(.+?)\]\((.+?)\)", text):
        path = (V3.parent / target).resolve()
        require(path.is_file(), "Unresolved image: " + target)
        image_records.append({"caption": caption, "path": str(path), "sha256": sha(path)})
    chinese = len(re.findall(r"[\u4e00-\u9fff]", text))
    main = text.split("# 第1章", 1)[1].split("# 参考文献", 1)[0]
    main_chinese = len(re.findall(r"[\u4e00-\u9fff]", main))
    require(main_chinese >= 5000, "Main text is below the course 5000-character floor")
    require("待填写" not in text, "Unresolved placeholder")
    require("<!--" not in text.replace("<!--TOC-->", ""), "Unresolved draft marker")
    QA.mkdir(parents=True, exist_ok=True)
    V3.write_text(text.rstrip() + "\n", encoding="utf-8")
    report = {"source": str(V2), "source_sha256": sha(V2), "output": str(V3), "output_sha256": sha(V3),
              "authorization": "User's final-optimization attachment and caller's scoped revision task",
              "operations": revision.ops, "bibliography_mapping_old_to_new": reference_mapping,
              "number_mapping": number_mapping, "chinese_characters_all": chinese,
              "main_text_chinese_characters": main_chinese, "images": image_records,
              "protocol_sha256": sha(RESULTS / "protocol.json"),
              "selection_sha256": sha(RESULTS / "selection_locked.json"),
              "release_input_sha256": sha(inputs["release_path"])}
    (QA / "revision_manifest.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    write_log(report, inputs)
    return text


def write_log(report: dict, inputs: dict) -> None:
    lines = ["# V3最终优化修订记录", "", "V2与V1原稿、Word和原实验均保留，V3从V2精确锚点替换及新增段落生成。此记录描述本次实际操作，不声称执行了未运行的正式多轮期刊审稿流水线。", "",
             "## 修改范围", "", "|操作|原因|", "|---|---|", *[f"|{i}|{op['reason']}|" for i, op in enumerate(report["operations"], 1)], "",
             f"V2 SHA256：`{report['source_sha256']}`。V3 SHA256：`{report['output_sha256']}`。完整精确前后文本与哈希见`paper/qa/v3/revision_manifest.json`。", "",
             "## 学校格式依据", "", f"采用[福州大学官方撰写规范]({OFFICIAL})。执行双语摘要、A4、上左25mm/下右20mm、小四宋体、正文固定20pt、分章另页、章内图表公式编号、奇偶篇眉、前置部分与正文独立页码、无表格左右边框及GB/T7714顺序引用。课程通知的5000字门槛优先，不附加毕业流程要求。", "",
             "## 科学结果边界", "", "原始实验、新工件重推与12组新训练分别保留；验证选型在最终测试阶段之前冻结，旧测试集已查看，新增指标不是新的盲测。标准差是三个训练种子的样本标准差，不是患者置信区间。RR方案含新增输入与可训练分支，归因图不证明医学机制。", "",
             "## 新增文献与阅读范围", "",
             "- Oliveira等2024：公开arXiv原文/摘要，用于近期背景，不将预印本写为正式期刊或比较跨协议成绩。https://arxiv.org/abs/2404.15367v2",
             "- Chen等2024：Computing in Cardiology公开会议论文，用于波形与间期背景。https://cinc.org/archives/2024/pdf/CinC2024-463.pdf",
             "- Lin等2017：Focal Loss公开原文，用于损失方法说明；本稿明确以arXiv资源著录。https://arxiv.org/abs/1708.02002",
             "- Sundararajan等2017：PMLR正式会议记录，用于Integrated Gradients方法。https://proceedings.mlr.press/v70/sundararajan17a.html", "",
             "## 待由最终渲染验收确认", "", "本脚本写源稿不代表Word/PDF已通过视觉验收。DOCX需由调用者在运行artifact marker后生成，再以真实Word更新目录/页码并导出PDF，检查封面、摘要、表格跨页、公式和全部页面。", "",
             f"正文汉字计数（不含前置及参考文献）：{report['main_text_chinese_characters']}；全稿汉字数：{report['chinese_characters_all']}。"]
    (PAPER / "review/final_v3_revision_log.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_docx(text: str) -> None:
    from docx import Document
    from docx.enum.section import WD_SECTION_START
    from docx.enum.style import WD_STYLE_TYPE
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Inches, Mm, Pt, RGBColor
    from PIL import Image

    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
          "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}
    with ZipFile(V2_DOCX) as archive:
        from lxml import etree as E
        original_xml = E.fromstring(archive.read("word/document.xml"))
        math = [deepcopy(p.find("m:oMath", ns)) for p in original_xml.findall(".//w:p", ns)
                if p.find("m:oMath", ns) is not None]
    require(len(math) == 7, "Expected the seven editable equations in V2")
    document = Document(V2_DOCX)
    body = document._element.body
    children = list(body)
    cover_break = next(i for i, x in enumerate(children) if x.find(qn("w:pPr")) is not None
                       and x.find(qn("w:pPr")).find(qn("w:sectPr")) is not None)
    end_section = deepcopy(body.sectPr)
    for child in children[cover_break + 1:]:
        body.remove(child)
    body.append(end_section)
    # Word pads restarted sections to matching sheet parity when this global
    # flag is enabled. A PAGE-based header field preserves the required odd/
    # even text without inserting empty verso pages into the electronic copy.
    document.settings.odd_and_even_pages_header_footer = False
    # The supplied cover's Normal style has a two-character indent.  Remove
    # character-unit inheritance so explicit body, heading and table widths work.
    # The WPS-derived template contains *two* Normal definitions (IDs 1/a0).
    # Word merges them on open, so clearing only python-docx's first match
    # silently restores the second definition's two-character indentation.
    for normal in document.styles.element.findall("w:style", ns):
        name = normal.find("w:name", ns)
        if name is None or name.get(qn("w:val")) != "Normal":
            continue
        normal_ind = normal.find("w:pPr/w:ind", ns)
        if normal_ind is not None:
            for attribute in ("firstLineChars", "hangingChars", "leftChars", "rightChars"):
                normal_ind.attrib.pop(qn("w:" + attribute), None)
            normal_ind.set(qn("w:firstLine"), "0")

    def font(run, size=12, bold=False, east="宋体", latin="Times New Roman"):
        run.font.name = latin; run.font.size = Pt(size); run.font.bold = bold
        run.font.color.rgb = RGBColor(0, 0, 0)
        fonts = run._element.get_or_add_rPr().rFonts
        if fonts is None:
            fonts = OxmlElement("w:rFonts"); run._element.get_or_add_rPr().insert(0, fonts)
        for key, value in (("eastAsia", east), ("ascii", latin), ("hAnsi", latin)):
            fonts.set(qn("w:" + key), value)

    def style(name, size=12, bold=False, east="宋体", line=20, after=0, before=0, outline=None):
        s = document.styles[name] if name in document.styles else document.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        s.base_style = document.styles["Normal"]
        s.font.name = "Times New Roman"; s.font.size = Pt(size); s.font.bold = bold
        s.font.color.rgb = RGBColor(0, 0, 0)
        fonts = s.element.get_or_add_rPr().rFonts
        if fonts is None:
            fonts = OxmlElement("w:rFonts"); s.element.get_or_add_rPr().insert(0, fonts)
        for key, value in (("eastAsia", east), ("ascii", "Times New Roman"), ("hAnsi", "Times New Roman")):
            fonts.set(qn("w:" + key), value)
        pf = s.paragraph_format
        pf.left_indent = Pt(0); pf.right_indent = Pt(0); pf.first_line_indent = Pt(0)
        pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY; pf.line_spacing = Pt(line)
        pf.space_before = Pt(before); pf.space_after = Pt(after); pf.widow_control = True
        if outline is not None:
            old = s.element.get_or_add_pPr().find(qn("w:outlineLvl"))
            if old is None:
                old = OxmlElement("w:outlineLvl"); s.element.get_or_add_pPr().append(old)
            old.set(qn("w:val"), str(outline)); pf.keep_with_next = True
        return s

    body_style = style("V3Body")
    body_style.paragraph_format.first_line_indent = Pt(24)
    body_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    style("V3Chapter", 18, True, "黑体", 20, 30, outline=0).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style("V3Heading2", 16, True, "黑体", 20, 18, outline=1)
    style("V3Heading3", 15, True, "黑体", 20, 12, outline=2)
    style("V3Title", 18, True, "黑体", 30, 6).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style("V3Subtitle", 14, True, "黑体", 24, 12).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style("V3AbstractHeading", 14, True, "黑体", 24, 12).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style("V3TOCHeading", 14, True, "黑体", 24, 12).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style("V3English", 12, False, "宋体", 16).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    style("V3Caption", 10.5, False, "宋体", 16, 6, 6).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    style("V3Table", 10.5, False, "宋体", 14)
    style("V3Reference", 10.5, False, "宋体", 17, 0, 3)
    document.styles["V3Reference"].paragraph_format.left_indent = Pt(21)
    document.styles["V3Reference"].paragraph_format.first_line_indent = Pt(-21)
    document.styles["V3Reference"].paragraph_format.keep_together = True
    style("V3Figure", 10.5, False, "宋体", 12, 0, 14).paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    document.styles["V3Figure"].paragraph_format.keep_with_next = True
    document.styles["V3Figure"].paragraph_format.line_spacing_rule = WD_LINE_SPACING.SINGLE
    document.styles["V3Figure"].paragraph_format.line_spacing = 1.0
    style("V3Equation", 12, False, "宋体", 28, 14, 14)
    for level in range(1, 4):
        st = style("TOC " + str(level), 10.5, False, "宋体", 20)
        st.paragraph_format.left_indent = Pt((level - 1) * 18)

    # Preserve the school-name artwork and original cover objects, changing
    # only the authorized text and margin/page properties.
    cover_paragraphs = document.paragraphs[:cover_break]
    def set_cover(index, value, size=14, label=None):
        p = cover_paragraphs[index]
        for child in list(p._p):
            if child.tag != qn("w:pPr"):
                p._p.remove(child)
        run = p.add_run((label or "") + value)
        font(run, size, east="黑体" if index in (3, 5, 6) else "宋体", bold=index in (3, 5, 6))
        p.paragraph_format.line_spacing = Pt(24)
    set_cover(3, "医学人工智能课程论文", 18)
    set_cover(5, TITLE, 16, "题    目：")
    set_cover(6, SUBTITLE, 14)
    set_cover(7, "吴江彬", 14, "姓    名：")
    set_cover(9, "102400329", 14, "学    号：")
    set_cover(11, "计算机与大数据学院", 14, "学    院：")
    set_cover(13, "软件工程", 14, "专    业：")
    set_cover(15, "2024级", 14, "年    级：")
    set_cover(17, "胡桓", 14, "教    师：")
    set_cover(19, "2026年11月17日", 14)

    def section_format(section, page_format=None, start=None):
        section.page_width = Mm(210); section.page_height = Mm(297)
        section.top_margin = Mm(25); section.left_margin = Mm(25)
        section.bottom_margin = Mm(20); section.right_margin = Mm(20)
        section.header_distance = Mm(12); section.footer_distance = Mm(10)
        # A continuous section plus an explicit first-paragraph page break
        # avoids Word inserting an unnumbered even page when numbering restarts.
        section.start_type = WD_SECTION_START.CONTINUOUS
        for ref in list(section._sectPr):
            if ref.tag in (qn("w:headerReference"), qn("w:footerReference")):
                section._sectPr.remove(ref)
        pg = section._sectPr.find(qn("w:pgNumType"))
        if pg is not None:
            section._sectPr.remove(pg)
        if page_format:
            pg = OxmlElement("w:pgNumType"); pg.set(qn("w:fmt"), page_format)
            if start is not None:
                pg.set(qn("w:start"), str(start))
            section._sectPr.append(pg)
        for container in (section.header, section.even_page_header, section.footer, section.even_page_footer):
            container.is_linked_to_previous = False
            for p in container.paragraphs:
                for child in list(p._p):
                    if child.tag != qn("w:pPr"):
                        p._p.remove(child)

    section_format(document.sections[0])
    section_format(document.sections[1], "upperRoman", 1)

    def page_field(container):
        p = container.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for kind in ("begin", "instr", "separate", "end"):
            run = p.add_run(); font(run, 10.5)
            el = OxmlElement("w:instrText" if kind == "instr" else "w:fldChar")
            if kind == "instr":
                el.text = " PAGE "
            else:
                el.set(qn("w:fldCharType"), kind)
            run._r.append(el)

    def alternating_header(p):
        def token(kind, text=None):
            run = p.add_run(); font(run, 10.5)
            el = OxmlElement("w:instrText" if kind == "instr" else "w:fldChar")
            if kind == "instr":
                el.set(qn("xml:space"), "preserve"); el.text = text
            else:
                el.set(qn("w:fldCharType"), kind)
            run._r.append(el)
        token("begin"); token("instr", " IF ")
        token("begin"); token("instr", " = MOD(")
        token("begin"); token("instr", " PAGE \\* Arabic "); token("separate"); token("end")
        token("instr", ", 2) "); token("separate"); token("end")
        token("instr", f' = 1 "{TITLE}" "福州大学本科生毕业设计（论文）" ')
        token("separate"); token("end")
    for container in (document.sections[1].footer, document.sections[1].even_page_footer):
        page_field(container)

    def inline(p, value, refs=False):
        # Source Markdown uses only numeric bibliographic citations.  Narrative
        # "文献[n]" stays on the baseline; parenthetic citations are superscript.
        parts = re.split(r"(\[\d+(?:[-,]\d+)*\])", value)
        cursor = 0
        for part in parts:
            run = p.add_run(part)
            if not refs and re.fullmatch(r"\[\d+(?:[-,]\d+)*\]", part):
                run.font.superscript = not value[:cursor].endswith("文献")
            cursor += len(part)

    def paragraph(value, name="V3Body"):
        p = document.add_paragraph(style=name); inline(p, value, name == "V3Reference")
        return p

    lines = text.splitlines(); i = 0; english = False; reference = False; in_body = False; formula_index = 0
    while i < len(lines):
        line = lines[i].strip(); i += 1
        if not line:
            continue
        if line == "# " + TITLE:
            paragraph(TITLE, "V3Title").paragraph_format.page_break_before = True; continue
        if line.startswith("副标题："):
            paragraph(line.removeprefix("副标题："), "V3Subtitle"); continue
        if line == "## 摘要":
            paragraph("摘  要", "V3AbstractHeading"); continue
        if line == "## Abstract":
            document.add_page_break(); english = True
            p = paragraph(EN_TITLE, "V3Subtitle")
            for r in p.runs: font(r, 15, True, latin="Arial Black")
            p = paragraph(EN_SUBTITLE, "V3Subtitle")
            for r in p.runs: font(r, 12, True, latin="Arial Black")
            p = paragraph("Abstract", "V3AbstractHeading")
            for r in p.runs: font(r, 14, True, latin="Arial Black")
            continue
        if line == "<!--TOC-->":
            document.add_page_break(); english = False
            paragraph("目  录", "V3TOCHeading")
            p = document.add_paragraph()
            for kind, value in (("begin", None), (None, 'TOC \\t "V3AbstractHeading,1,V3Chapter,1,V3Heading2,2,V3Heading3,3" \\h \\z'), ("separate", None)):
                run = p.add_run(); element = OxmlElement("w:instrText" if kind is None else "w:fldChar")
                if kind is None: element.text = value
                else: element.set(qn("w:fldCharType"), kind)
                run._r.append(element)
            p.add_run("目录由Word更新")
            run = p.add_run(); element = OxmlElement("w:fldChar"); element.set(qn("w:fldCharType"), "end"); run._r.append(element)
            continue
        if line.startswith("# "):
            title = line[2:]
            if title.startswith("第1章"):
                main_section = document.add_section(WD_SECTION_START.NEW_PAGE)
                section_format(main_section, "decimal", 1)
                for container, value in ((main_section.header, TITLE),
                                         (main_section.even_page_header, "福州大学本科生毕业设计（论文）")):
                    p = container.paragraphs[0]; p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.paragraph_format.first_line_indent = Pt(0)
                    if value == TITLE:
                        alternating_header(p)
                    else:
                        font(p.add_run(value), 10.5)
                    borders = OxmlElement("w:pBdr"); border = OxmlElement("w:bottom")
                    border.set(qn("w:val"), "single"); border.set(qn("w:sz"), "4"); border.set(qn("w:color"), "000000")
                    borders.append(border); p._p.get_or_add_pPr().append(borders)
                page_field(main_section.footer); page_field(main_section.even_page_footer)
                in_body = True
            else:
                document.add_page_break()
            p = paragraph(title, "V3Chapter")
            if title.startswith("第1章"):
                p.paragraph_format.page_break_before = True
            reference = title == "参考文献"
            continue
        if line.startswith("### "):
            paragraph(line[4:], "V3Heading3"); continue
        if line.startswith("## "):
            paragraph(line[3:], "V3Heading2"); continue
        if line.startswith("!["):
            match = re.fullmatch(r"!\[(.+)\]\((.+)\)", line)
            require(match is not None, "Invalid image source")
            path = (V3.parent / match[2]).resolve()
            with Image.open(path) as image:
                width = min(6.35, 5.6 * image.width / image.height)
                if path.name == "system_comparison_cards.png": width = min(width, 3.9)
            p = document.add_paragraph(style="V3Figure")
            p.add_run().add_picture(str(path), width=Inches(width))
            paragraph(match[1], "V3Caption")
            continue
        if re.match(r"表\d+-\d+\s", line):
            p = paragraph(line, "V3Caption"); p.paragraph_format.keep_with_next = True
            continue
        if line.startswith("|"):
            values = [line]
            while i < len(lines) and lines[i].strip().startswith("|"):
                values.append(lines[i].strip()); i += 1
            values = [v for v in values if not re.fullmatch(r"\|[\s:|\-]+", v)]
            cells = [[s.strip() for s in v.strip("|").split("|")] for v in values]
            n = len(cells[0]); require(all(len(r) == n for r in cells), "Unequal table columns")
            table_obj = document.add_table(rows=0, cols=n); table_obj.alignment = WD_TABLE_ALIGNMENT.CENTER
            table_obj.autofit = False
            # Numeric result columns need comparable widths, while narrative
            # project tables reserve room for their explanations.
            if n == 3: weights = [1.0, 2.8, 2.2]
            elif n == 4: weights = [1.35, 1.5, 1.5, 1.65]
            elif n == 5: weights = [1.25, .75, 1.33, 1.33, 1.34]
            else: weights = [1.0] * n
            widths = [6.35 * w / sum(weights) for w in weights]
            for col, width in zip(table_obj.columns, widths): col.width = Inches(width)
            borders = OxmlElement("w:tblBorders")
            for edge in ("top", "bottom", "left", "right", "insideH", "insideV"):
                node = OxmlElement("w:" + edge)
                node.set(qn("w:val"), "single" if edge in ("top", "bottom", "insideH") else "nil")
                node.set(qn("w:sz"), "4"); node.set(qn("w:color"), "000000")
                borders.append(node)
            table_obj._tbl.tblPr.append(borders)
            for index, values_row in enumerate(cells):
                row = table_obj.add_row(); row._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
                if index == 0: row._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
                for cell, value, width in zip(row.cells, values_row, widths):
                    cell.width = Inches(width); cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
                    p = cell.paragraphs[0]; p.style = "V3Table"
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER if len(value) < 26 else WD_ALIGN_PARAGRAPH.LEFT
                    inline(p, value)
                    p.paragraph_format.keep_with_next = index < len(cells)-1 if len(cells) <= 12 else index == 0
                    for run in p.runs:
                        run.bold = index == 0
                        if n >= 6: run.font.size = Pt(9.5)
                    if index == 0:
                        sh = OxmlElement("w:shd"); sh.set(qn("w:fill"), "F2F2F2"); cell._tc.get_or_add_tcPr().append(sh)
            document.add_paragraph().paragraph_format.space_after = Pt(0)
            continue
        if line.startswith("$$"):
            require(formula_index < len(math), "Unexpected extra source equation")
            match = re.search(r"（([\d-]+)）", line)
            p = document.add_paragraph(style="V3Equation")
            from docx.enum.text import WD_TAB_ALIGNMENT
            p.paragraph_format.tab_stops.clear_all()
            p.paragraph_format.tab_stops.add_tab_stop(Inches(3.17), WD_TAB_ALIGNMENT.CENTER)
            p.paragraph_format.tab_stops.add_tab_stop(Inches(6.35), WD_TAB_ALIGNMENT.RIGHT)
            p.add_run("\t"); p._p.append(deepcopy(math[formula_index])); formula_index += 1
            p.add_run("\t（" + match[1] + "）")
            continue
        if line.startswith("关键词："):
            p = paragraph(line, "V3Body"); p.paragraph_format.first_line_indent = Pt(0)
            p.paragraph_format.line_spacing = Pt(16)
            for r in p.runs: r.bold = True
        elif line.startswith("Key words:"):
            p = paragraph(line, "V3English")
            for r in p.runs: font(r, 12, True, latin="Arial Black")
        else:
            paragraph(line, "V3Reference" if reference else "V3English" if english else "V3Body")
    require(in_body and formula_index == 7, "Body/equation parsing was incomplete")
    document.core_properties.title = TITLE
    document.core_properties.subject = "医学人工智能课程论文"
    document.core_properties.author = "吴江彬"
    document.core_properties.keywords = "ECG-AI; MIT-BIH; 心拍分类; 课程论文"
    update = document.settings.element.find(qn("w:updateFields"))
    if update is None: update = OxmlElement("w:updateFields"); document.settings.element.append(update)
    update.set(qn("w:val"), "true")
    DOCX.parent.mkdir(parents=True, exist_ok=True)
    document.save(DOCX)
    check_docx(DOCX)


def check_docx(path: Path) -> dict:
    from lxml import etree as E
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
          "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}
    with ZipFile(path) as archive:
        bad = archive.testzip(); require(bad is None, "Corrupt DOCX entry: " + str(bad))
        doc = E.fromstring(archive.read("word/document.xml"))
        text = "".join(doc.xpath(".//w:t/text()", namespaces=ns))
        require("软件工程" in text and "102400329" in text and "吴江彬" in text, "Cover fields missing")
        require("待填写" not in text, "Placeholder remains in DOCX")
        require(len(doc.findall(".//m:oMath", ns)) == 7, "Seven native equations required")
        sections = doc.findall(".//w:sectPr", ns)
        require(len(sections) == 3, "Cover/frontmatter/body sections expected")
        for s in sections:
            margin = s.find("w:pgMar", ns)
            require(margin is not None, "Section has no margins")
            require(abs(int(margin.get("{" + ns["w"] + "}top")) - 1417) <= 2, "Top margin is not 25 mm")
        for table_obj in doc.findall(".//w:tbl", ns):
            require(table_obj.find("w:tr/w:trPr/w:tblHeader", ns) is not None, "Table header is not repeatable")
        info = {"docx": str(path), "sha256": sha(path), "native_equations": 7,
                "tables": len(doc.findall(".//w:tbl", ns)), "sections": len(sections),
                "zip_integrity": "PASS", "visual_qa": "PENDING: actual Word/PDF render required"}
    QA.mkdir(parents=True, exist_ok=True)
    (QA / "docx_structural_check.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    return info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-inputs", type=Path, default=QA / "release_inputs.json")
    parser.add_argument("--build-draft", action="store_true")
    parser.add_argument("--build-docx", action="store_true")
    parser.add_argument("--check-docx", type=Path)
    args = parser.parse_args()
    if args.check_docx:
        print(json.dumps(check_docx(args.check_docx), ensure_ascii=False, indent=2)); return
    inputs = load_inputs(args.release_inputs)
    if not (args.build_draft or args.build_docx):
        print("Completed scientific and software inputs verified; no manuscript was written"); return
    text = build_draft(inputs) if args.build_draft else V3.read_text(encoding="utf-8")
    if args.build_docx:
        require(V3.is_file(), "V3 source is missing")
        build_docx(text)
    print(json.dumps({"draft": str(V3) if args.build_draft else None,
                      "docx": str(DOCX) if args.build_docx else None,
                      "source_v2_unchanged": sha(V2) == V2_SHA}, ensure_ascii=False))


if __name__ == "__main__":
    main()
