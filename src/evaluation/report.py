"""Assemble the course-project report from the exported artifacts and metrics."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd


def _table(frame: pd.DataFrame, columns: list[str] | None = None) -> str:
    if columns:
        frame = frame[columns]
    def display(value):
        if isinstance(value, float):
            return f"{value:.4f}"
        return str(value).replace("|", "\\|").replace("\n", " ")
    headers = [str(column) for column in frame.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(display(value) for value in row) + " |" for row in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def _report_relative_image(root: Path, report_dir: Path, value: str | Path) -> str:
    image_path = Path(value)
    if not image_path.is_absolute():
        image_path = root / image_path
    return Path(os.path.relpath(image_path.resolve(), report_dir.resolve())).as_posix()


def _metric_table(metrics: dict, class_names: list[str]) -> str:
    rows = []
    for model, values in metrics.items():
        row = {"model": model, "accuracy": values["accuracy"], "macro-F1": values["macro_f1"]}
        for group in class_names:
            row[f"{group} precision"] = values["per_class"][group]["precision"]
            row[f"{group} recall"] = values["per_class"][group]["recall"]
            row[f"{group} F1"] = values["per_class"][group]["f1"]
            row[f"{group} n"] = values["per_class"][group]["support"]
        rows.append(row)
    return _table(pd.DataFrame(rows))


def _error_summary(result_dir: Path, class_names: list[str]) -> tuple[str, str]:
    lines = []
    examples = []
    for model in ("logistic_regression", "random_forest", "cnn_1d"):
        path = result_dir / f"test_predictions_{model}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path, keep_default_na=False)
        errors = frame[~frame.correct]
        if errors.empty:
            lines.append(f"- **{model}**：测试集未出现误分类。")
            continue
        counts = errors.groupby(["true_aami_label", "predicted_aami_label"]).size().sort_values(ascending=False)
        top = counts.head(5)
        lines.append(f"- **{model}**：共 {len(errors):,}/{len(frame):,} 个测试样本误分类；主要方向：" +
                     "、".join(f"{a}→{b} {int(n)} 拍" for (a, b), n in top.items()) + "。")
        chosen = (errors.sort_values(["record_id", "annotation_sample"])
                  .groupby("record_id", sort=True, as_index=False).head(1).head(8))
        examples.extend({"model": model, "sample_id": row.sample_id, "record_id": row.record_id,
                         "subject_id": row.subject_id, "annotation_sample": int(row.annotation_sample),
                         "time_s": float(row.time_s), "lead_name": row.lead_name,
                         "true": row.true_aami_label, "predicted": row.predicted_aami_label}
                        for row in chosen.itertuples())
    example_text = "\n".join(f"- `{row['model']}`：{row['record_id']} / {row['subject_id']} / {row['lead_name']}，"
                              f"样本 {row['annotation_sample']}（{row['time_s']:.3f}s），"
                              f"{row['true']}→{row['predicted']}。" for row in examples)
    return "\n".join(lines) if lines else "尚无已完成模型的锁定测试集预测。", example_text or "尚无误分类样本可列。"


def _experiment_section(root: Path, task: str, heading: str) -> str:
    from ..classify import TASKS
    spec = TASKS[task]
    marker = root / spec["result"] / "experiment.json"
    if not marker.exists():
        return f"## {heading}\n\n尚未运行；此部分不会推测或填写模型指标。\n"
    experiment = json.loads(marker.read_text(encoding="utf-8"))
    if experiment.get("status") != "completed":
        return f"## {heading}\n\n模型训练或评估尚未完成（当前状态：`{experiment.get('status','unknown')}`），不报告测试指标。\n"
    class_names = experiment["class_names"]
    metrics = experiment["test_metrics"]
    result_dir = marker.parent
    lines = [f"## {heading}", "", f"数据规模：训练 {experiment['train_samples']:,}，验证 {experiment['validation_samples']:,}，测试 {experiment['test_samples']:,} 拍。",
             "", "测试指标（由保存预测 CSV 独立重算核对）：", "", _metric_table(metrics, class_names), "",
             "### 混淆矩阵", ""]
    for model, score in metrics.items():
        lines.append(f"- **{model}**（行=参考标签、列=预测标签，类别顺序 {', '.join(class_names)}）：`{score['confusion_matrix']}`。")
    lines.extend(["", "### 误分类观察", "", _error_summary(result_dir, class_names)[0], "", "### 可追溯的错误样本", "",
                  _error_summary(result_dir, class_names)[1], "", "### 图像", ""])
    for entry in experiment.get("figures", []):
        figure_path = Path(entry["file"])
        relative = _report_relative_image(root, root / "reports/classification", figure_path)
        lines.append(f"- [{Path(relative).name}]({relative}) — {entry['purpose']}。")
    if task == "nv":
        lines.extend(["", f"重点 V 类指标：\n\n{_table(pd.DataFrame([
            {"model": model, "V precision": score["per_class"]["V"]["precision"],
             "V recall": score["per_class"]["V"]["recall"], "V F1": score["per_class"]["V"]["f1"],
             "V support": score["per_class"]["V"]["support"]} for model, score in metrics.items()]))}"])
    return "\n".join(lines) + "\n"


def generate_experiment_summary(root: Path) -> Path:
    root = root.resolve(); report_dir = root / "reports/classification"
    report_dir.mkdir(parents=True, exist_ok=True)
    dataset = root / "data/processed/mitdb44_nv_v1"
    data_section = "## 数据处理与划分\n\n数据集版本 1.0.0 共 48 条记录、47 位受试者；分析和分类数据使用 44 条非起搏记录，排除 102、104、107、217。PhysioNet 官方目录说明这四条记录包含起搏心拍，并指出原始模拟记录对起搏器伪迹的常见识别线索保真不足；44 条方案是常见 AAMI 实验约定，不意味着原始记录被删除。"
    data_section += " [PhysioNet 数据集说明](https://physionet.org/content/mitdb/1.0.0/)；[MIT-BIH 目录说明](https://physionet.org/physiobank/database/html/mitdbdir/intro.htm)。\n\n"
    if (dataset / "class_counts.csv").exists():
        counts = pd.read_csv(dataset / "class_counts.csv")
        data_section += "44 记录的 AAMI 目标心拍有效窗口数量：\n\n" + _table(counts) + "\n\n"
    full_label_path = root / "results/classification/dataset/raw_symbol_counts_all48.csv"
    by_record_label_path = root / "results/classification/dataset/raw_symbol_counts_by_record_all48.csv"
    if full_label_path.exists() and by_record_label_path.exists():
        raw_labels = pd.read_csv(full_label_path, keep_default_na=False)
        record_labels = pd.read_csv(by_record_label_path, keep_default_na=False)
        grouped = record_labels[record_labels.aami_label.astype(str).str.len() > 0].groupby(
            ["included_in_44_record_experiment", "aami_label"])["count"].sum().unstack(fill_value=0)
        rows = []
        for cohort, title in ((True, "44 included"), (False, "4 paced excluded")):
            values = grouped.loc[cohort] if cohort in grouped.index else pd.Series(dtype=int)
            rows.append({"record_cohort": title, **{g: int(values.get(g, 0)) for g in ("N", "S", "V", "F", "Q")}})
        rows.append({"record_cohort": "All 48", **{g: int(raw_labels.loc[raw_labels.aami_label == g, "count"].sum()) for g in ("N", "S", "V", "F", "Q")}})
        data_section += "原始标注中 AAMI 心拍总数（此处仅计心拍，不计节律/信号质量符号）：\n\n" + _table(pd.DataFrame(rows)) + "\n\n"
        data_section += "全 48 条记录的原始 symbol 频数（包含不入心拍类别的非心拍标注）：\n\n" + _table(raw_labels) + "\n\n"
    if (dataset / "split_manifest.csv").exists():
        manifest = pd.read_csv(dataset / "split_manifest.csv", keep_default_na=False)
        subject_counts = manifest.drop_duplicates("subject_id").groupby("split").size().reindex(["train", "val", "test"], fill_value=0)
        record_counts = manifest.groupby("split").record_id.agg(lambda values: ", ".join(map(str, values))).reindex(["train", "val", "test"], fill_value="")
        split_frame = pd.DataFrame({"split": subject_counts.index, "subject_count": subject_counts.to_numpy(),
                                    "record_count": manifest.groupby("split").record_id.size().reindex(subject_counts.index).to_numpy(),
                                    "records": record_counts.to_numpy()})
        data_section += "固定种子 20261027 的患者级划分：\n\n" + _table(split_frame) + "\n\n"
        data_section += "记录 201/202 同属一个受试者分组并进入同一集合；100/200 因前期已经用于数据探索而预先固定在训练集。受试者交集检查必须为零。"
    if (dataset / "split_class_counts.csv").exists():
        split_counts = pd.read_csv(dataset / "split_class_counts.csv")
        data_section += "\n\nN/V 数据集的分区类别数：\n\n" + _table(split_counts[split_counts.aami_label.isin(["N", "V"])]) + "\n"
    multi_dataset = root / "data/processed/mitdb44_nsvf_v1"
    if (multi_dataset / "split_class_counts.csv").exists():
        multi_counts = pd.read_csv(multi_dataset / "split_class_counts.csv")
        data_section += "\n\n复用同一患者分区后的四分类样本数量：\n\n" + _table(multi_counts) + "\n"
        subject_file = multi_dataset / "subject_sample_counts.csv"
        if subject_file.exists():
            by_subject = pd.read_csv(subject_file, keep_default_na=False)
            spread = by_subject.groupby(["split", "mapped_label"]).sample_count.agg(
                subject_count="count", heartbeat_count="sum", minimum_per_subject="min", maximum_per_subject="max").reset_index()
            data_section += "\n各类别在每个患者分区中出现的患者数与每患者心拍数量范围：\n\n" + _table(spread) + "\n"
    data_section += "\n预处理复用 `src.io.load_record`、`src.labels.AAMI_MAP` 和 `src.preprocessing`。先在连续 MLII（不存在时明确回退并记录实际首导联）上进行 0.5–40 Hz Butterworth SOS 双向滤波，标注前 0.3 秒、后 0.4 秒、含端点共 253 点；窗口越界、滤波保护区、非有限或平直窗按预定义技术规则排除并留在 metadata。通道/记录/样本/原标签均可追溯。全局均值与标准差仅在训练集有效过滤后样本拟合；Logistic Regression 的特征缩放同样只在训练数据拟合。类别权重只由训练标签计算。原始 48 条记录均保留且逐文件 SHA256 复核。"
    prep_catalog_paths = [root / "results/classification/dataset/figure_catalog.csv",
                          root / "results/classification/dataset/figure_catalog_nsvf_44.csv"]
    prep_entries = []
    for catalog_path in prep_catalog_paths:
        if catalog_path.exists():
            prep_entries.append(pd.read_csv(catalog_path, keep_default_na=False))
    if prep_entries:
        prep_figures = pd.concat(prep_entries, ignore_index=True).drop_duplicates("file")
        data_section += "\n\n### 数据构建与预处理图片\n\n"
        for entry in prep_figures.itertuples():
            relative = _report_relative_image(root, report_dir, entry.file)
            data_section += f"- [{Path(entry.file).name}]({relative}) — {entry.title}。\n"

    binary_section = _experiment_section(root, "nv", "N/V 二分类结果")
    multiclass_section = _experiment_section(root, "nsvf", "N/S/V/F 四分类结果")
    ablation_path = root / "results/classification/nsvf44_v1/class_weight_validation_ablation.json"
    if ablation_path.exists():
        ablation = json.loads(ablation_path.read_text(encoding="utf-8"))
        ablation_rows = []
        for model, weighted in ablation["weighted_baseline"].items():
            unweighted = ablation["unweighted_ablation"][model]
            for group in ("N", "S", "V", "F"):
                first = weighted["per_class"][group]; second = unweighted["per_class"][group]
                ablation_rows.append({"model": model, "class": group,
                                      "weighted Recall": first["recall"], "unweighted Recall": second["recall"],
                                      "Recall Δ": first["recall"]-second["recall"],
                                      "weighted F1": first["f1"], "unweighted F1": second["f1"],
                                      "weighted support": first["support"]})
        multiclass_section += "\n### 训练集类别权重的验证集消融\n\n"
        multiclass_section += "为观察训练类权重的作用，使用同一训练集/验证集、固定结构与种子另跑无权重 LR/RF/CNN 对照；该消融只读取训练和验证文件，**未读取测试文件，也未更换/挑选正式模型**。下面 Δ=正式训练权重模型验证 Recall − 无权重验证 Recall，不能视作测试效果或独立验证集。\n\n"
        multiclass_section += _table(pd.DataFrame(ablation_rows)) + "\n\n"
        weight_path = root / "results/classification/nsvf44_v1/training_class_weights.json"
        weight_info = json.loads(weight_path.read_text(encoding="utf-8")) if weight_path.exists() else {}
        weight_values = weight_info.get("inverse_frequency_balanced_weights", [])
        if isinstance(weight_values, dict):
            formatted_weights = ", ".join(f"{weight_values.get(group, float('nan')):.4f}" for group in ("N", "S", "V", "F"))
        else:
            formatted_weights = ", ".join(f"{float(value):.4f}" for value in weight_values)
        multiclass_section += "按训练集频数计算的正式类权重（N/S/V/F）为：`" + formatted_weights + "`。消融图：[`class_weight_validation_ablation.png`](../../figures/09_multiclass_classification/class_weight_validation_ablation.png)。\n"
    limitations = "## 当前限制与下一阶段建议\n\n"
    limitations += "- 结果仅反映本次固定受试者划分和 44 条非起搏 MIT-BIH 记录；数据源包含有意选择的少见心律片段，不是普通人群患病率样本。不能把分类结果描述为临床诊断。\n"
    limitations += "- 模型使用单导联 253 点心拍窗口，固定窗可能含邻拍；记录之间导联、患者形态和滤波影响仍存在。除患者级隔离外，窗口标注位置仍沿用专家 `.atr`，没有另做 R 峰检测或临床专家复核。\n"
    limitations += "- 44 记录的 S/F 在记录与患者之间分布稀疏；解释四分类时需同时报告每类样本支持数、患者数、Recall、Macro-F1 与混淆矩阵。不能通过随机心拍拆分增加稀有类测试量。\n"
    limitations += "- 下一阶段可开发课程演示用只读 Web 可视化：记录/导联/时间窗浏览、原始与滤波信号并列、标注位置及原始符号/AAMI 映射说明、可筛选类别分布、患者级分区说明、测试混淆矩阵和模型概率。明确注明版本/划分/模型哈希、概率非临床诊断，默认禁止浏览器上传或覆写原始数据；模型阈值/校准只在验证集拟定，测试集保持锁定。"

    text = ("# MIT-BIH 数据构建与心拍分类实验总结\n\n"
            "本报告由代码从实际数据集 manifest、预测 CSV 和指标 JSON 生成。该项目用于课程数据探索和算法实验，不构成临床诊断。\n\n"
            + data_section + "\n\n" + binary_section + "\n" + multiclass_section + "\n" + limitations + "\n"
            + "## 文件入口\n\n"
            + "- 数据预处理：`data/processed/mitdb44_nv_v1/` 与 `data/processed/mitdb44_nsvf_v1/`。\n"
            + "- 训练日志和预测：`results/classification/nv44_v1/`、`results/classification/nsvf44_v1/`。\n"
            + "- 模型权重：`checkpoints/nv44_v1/`、`checkpoints/nsvf44_v1/`。\n"
            + "- 图像：`figures/07_preprocessing/`、`figures/08_binary_classification/`、`figures/09_multiclass_classification/`。\n")
    target = report_dir / "experiment_summary.md"
    target.write_text(text, encoding="utf-8")
    return target
