"""Generate a Chinese report from computed tables, with hash-bound visual notes."""
import json
import platform
from importlib.metadata import version
from .labels import GROUPS


def markdown_table(frame, columns=None):
    frame = frame if columns is None else frame[columns]
    def cell(value):
        text = f"{value:.6g}" if isinstance(value, float) else str(value)
        return text.replace("|", "\\|").replace("\n", " ")
    lines = ["| " + " | ".join(map(str, frame.columns)) + " |",
             "| " + " | ".join("---" for _ in frame.columns) + " |"]
    lines += ["| " + " | ".join(cell(v) for v in row) + " |" for row in frame.itertuples(index=False, name=None)]
    return "\n".join(lines)


def build_report(root, records, tables, metadata, quality, beats, morphology, manifest, figure_table, config):
    raw, classes = tables["raw_symbol_counts"], tables["aami_counts"]
    annotations = sum(r.annotations.shape[0] for r in records)
    total = int(classes["count"].sum())
    positive = classes[classes["count"] > 0].sort_values("count", ascending=False)
    biggest = positive.iloc[0] if not positive.empty else None
    smallest = positive.iloc[-1] if not positive.empty else None
    missing = classes.loc[classes["count"] == 0, "aami_group"].tolist()
    kinds = raw.groupby("annotation_kind")["count"].sum().to_dict()
    nonbeat = kinds.get("non_beat", 0)
    unmapped = kinds.get("unmapped_beat", 0)
    unknown = kinds.get("unknown", 0)
    notes_path = root / "reports" / "visual_review.json"
    notes = "本次输出尚未附加与原始文件哈希匹配的视觉核查。下文自动统计不能代替逐段质量复核。"
    if notes_path.exists():
        review = json.loads(notes_path.read_text(encoding="utf-8"))
        raw_hashes = {m["file"]: m["sha256"] for m in manifest if m["file"].endswith((".dat", ".hea", ".atr"))}
        if review.get("raw_sha256") == raw_hashes and review.get("window_s") == [config['pre_s'], config['post_s']]:
            notes = "\n\n".join(review["observations"])
    imbalance = f"最多的非空组为 {biggest.aami_group}（{int(biggest['count'])} 拍），最少的非空组为 {smallest.aami_group}（{int(smallest['count'])} 拍），两者数量比为 {biggest['count']/smallest['count']:.2f}:1。" if biggest is not None else "没有已映射心拍。"
    non_n = int(classes.loc[classes.aami_group != "N", "count"].sum())
    text = f"""# MIT-BIH 第一阶段数据探索报告

## 数据集简介与本次范围

分析数据库版本固定为 **MIT-BIH Arrhythmia Database 1.0.0**。官方数据库含 48 条约半小时的双通道记录，来自 47 位受试者，采样率为每导联 360 Hz。部分记录为富集少见心律失常而选取，因此本次比例不能解释为人群患病率。[PhysioNet 官方说明](https://physionet.org/content/mitdb/1.0.0/)

本次实际读取记录：**{', '.join(r.name for r in records)}**；共 {len(records)} 条。下列统计均由本地原始文件计算；不是全库统计。未训练模型、未划分训练/测试集、未开发前端，未滤波、未重采样、未修改原始信号或专家标注。

{markdown_table(metadata, ['record','fs_hz','samples','duration_s','last_sample_time_s','leads','units','annotation_count'])}

## 数据读取流程与对应验证

1. 从 `https://physionet.org/files/mitdb/1.0.0/` 下载官方 `RECORDS`、`SHA256SUMS.txt` 和所选记录的 `.dat/.hea/.atr`。已有原始文件仅核验不覆盖；不匹配即报错。下载清单为 `results/download_manifest.csv`。官方哈希表本身通过 HTTPS 获取；这属于完整性核验，不是独立数字签名认证。
2. 使用 `wfdb.rdheader` 解析头文件；`wfdb.rdrecord` 分别读取物理幅值与数字采样；`wfdb.rdann(..., 'atr')` 读取专家标注。[WFDB Python 官方文档](https://wfdb.readthedocs.io/en/latest/io.html)
3. 时间采用记录起点相对时间 `time_s = sample / fs`，从 0 编号。有效末采样时间是 `(n-1)/fs`，记录区间为 `[0,n/fs)`。导联名称、物理单位、原始注释均来自头文件；完整元数据见 `results/record_metadata.csv`。
4. 核对信号形状、采样率、数字信号逐导联校验和、标注范围/顺序、重复时间及心拍位置有限值。图中标记直接放到原始 `sample`，不以检测峰替换。位置落在 QRS 附近的视觉对应只能支持读入一致，不能独立验证专家标签的医学正确性。

{markdown_table(metadata, ['record','annotations_in_range','annotations_monotonic','duplicate_annotation_times','duplicate_beat_times','all_signal_samples_finite','all_beat_positions_finite','digital_checksums_match'])}

## 原始标签、AAMI 归组及依据

WFDB 原始 `symbol` 是事实来源；中文仅是官方符号定义的翻译。映射严格使用任务指定的常用 AAMI 五组规则：`N←N,L,R,e,j`；`S←A,a,J,S`；`V←V,E`；`F←F`；`Q←/,f,Q`。参考 [de Chazal 等，2004，Table I，DOI](https://doi.org/10.1109/TBME.2004.827359)；原始符号含义及非心拍定义见 [PhysioNet Standard annotations](https://physionet.org/static/lightwave/doc/annotations.html)。本阶段是五类映射探索，不宣称已经完成完整 AAMI 评测协议。

**原始 N 与分组 N 不同**：分组 N 还包含束支阻滞及部分逸搏，不能统称健康/正常。原始 Q 与分组 Q 也不同：分组 Q 包含起搏和起搏融合。非心拍标注不放入五组；已知但不在指定映射中的心拍单列 `unmapped_beat`；陌生符号列为 `unknown`，不推测归组。

实际出现的所有原始符号如下（0 次符号只在完整映射 CSV 中列出）：

{markdown_table(raw)}

完整规则、中文含义、分组、数量及来源：`results/label_mapping.csv`；分记录原始计数：`results/raw_symbol_counts_by_record.csv`；逐条非心拍：`results/non_beat_annotations.csv`。全部标注含 `record, annotation_index, sample, time_s, symbol, subtype, chan, num, aux_note`，并保留对应导联幅值。部分原始 aux_note 含 NUL 终止符，另以 `aux_note_json` 保留可安全往返的 JSON 字符串、`aux_note_text` 展示去尾部 NUL 的文本；`results/annotations.jsonl` 无损保留原始 aux_note 并做往返验证。

## 统计事实与各类别分布

总标注 **{annotations}** 条 = 五组已映射心拍 **{total}** + 非心拍 **{nonbeat}** + 未映射心拍 **{unmapped}** + 未识别 **{unknown}**。同一心拍在两个导联上观察只计一次。

{markdown_table(classes)}

{imbalance} 零样本组：{', '.join(missing) or '无'}。比例分母仅为已映射心拍（{total}）；非心拍和未映射项不悄悄并入分母。非 N 组共 {non_n} 拍，不能直接解释为经诊断的“异常总数”。

{markdown_table(tables['aami_counts_by_record'])}

![类别数量与占比](../figures/aami_class_distribution.png)

![记录间类别分布](../figures/aami_distribution_by_record.png)

## 典型波形与同类差异

绘图片段默认以原始专家标注为中心，前 {config['pre_s']} s、后 {config['post_s']} s，采样端点包含中心及末点。仅对完整窗口作图：{len(beats)} 个已识别心拍中，{int(beats.window_valid.sum())} 个窗口有效，{int((~beats.window_valid).sum())} 个越界跳过；统计计数仍保留全部心拍。有效窗口也可能含相邻心拍，不保证是严格孤立心拍。

第一组图展示每条记录双导联前 10 秒原始幅值，第二组在同一时间轴叠加原始符号。每记录的 `*_class_examples.png` 对每组取时间排序的中间有效心拍；`*_within_class.png` 等间距取最多 6 个有效心拍，左图原幅值，右图仅为展示减去各窗口中位数，未改写数据。缺失类别明确留空，不生成假波形。主比较导联优先 MLII，不存在则用头文件首导联；均标明实际导联。

{notes}

以下为全部有效窗口的峰峰值与相邻 RR 中位数。它们是描述量，**不是 QRS 宽度、纯目标心拍幅值或疾病指标**，会受到邻拍、基线和噪声影响；不能用这些量反推或改写标签。

{markdown_table(morphology)}

## 数据质量问题

{markdown_table(quality, ['record','lead','unit','minimum','maximum','nonfinite_samples','max_abs_sample_difference','adc_rail_samples','longest_exact_flat_run_s'])}

每导联完整统计（均值、标准差、1%/99%分位数、数字值范围及 ADC 上下轨）见 `results/signal_quality.csv`。全记录共发现 {int(quality.nonfinite_samples.sum())} 个非有限采样、{int(quality.adc_rail_samples.sum())} 个到达/越过头文件 ADC 轨值的采样。没有缺失值或触轨不意味着没有噪声；原始幅值大小也不能直接判定信号质量或疾病。

每 10 秒窗口计算一阶差分 RMS 和峰峰值（含不足 10 秒的尾窗），见 `results/quality_windows.csv`；对每导联差分 RMS 最大的窗口绘出双导联检查图，另绘第一处非初始 `~` 附近窗口（存在时）。差分 RMS 同时受 QRS 形态、心率、陡变和高频噪声影响，**不是噪声检测器或经验证的质量评分**，不据此删除样本或计算“噪声比例”。`~` 是质量变化事件，`|` 是类 QRS 伪迹；保留其 subtype/chan/aux_note，不将事件次数当作噪声持续时长，也不误认作 Q 类心拍。

官方目录另指出记录 100 整体较干净，记录 200 的下导联存在较重噪声和伪迹，上导联偶有高频噪声；这是外部记录说明，不是本程序新作出的诊断或质量标注。[官方记录目录 100/200](https://physionet.org/files/mitdb/1.0.0/mitdbdir/records.htm)

## 针对七个问题的回答与后续 CNN 建议

1. **有哪些类型？** 上方原始符号表逐项列出当前记录的实际类型；五组计数与原始符号分别保留，不以全库类别冒充本次观察。
2. **最多/最少？** {imbalance} 零样本组为 {', '.join(missing) or '无'}；零样本与“最少非空类”分开说明。
3. **正常与其他组形态差异？** 以带记录、导联、时间的实际观察段为准。形态差异可以与既有专家标签相容，但不能单靠图像作新诊断；S 类与原始 N 常可能局部形态相近，需保留节律上下文。
4. **同类是否不同？** 见已核查的形态叠图与峰峰值范围；类内变化可能来自生理变化、导联方向、基线或噪声，本阶段不区分其因果贡献。
5. **噪声与异常幅值？** 见完整质量统计、专家质量/伪迹事件和高差分窗口。没有做全记录逐秒人工审阅，未给出无依据的异常幅值诊断。
6. **是否不平衡？** {imbalance} 当前子集的零样本类不能用来估计五类识别能力；记录间分布差异也需考虑。
7. **未来 CNN 需先处理什么？** 先扩展数据覆盖及稀有类别，定义起搏记录、Q、未映射心拍和非心拍的处理政策；根据任务决定导联与上下文窗口，检查高心率邻拍重叠、边界丢失及专家标注是否为预期的中心点。若采用滤波、去基线或重采样，保存参数并验证波形失真与坐标换算；原始数据继续只读保留。

未来必须先按**患者独立分组**设计训练/验证/测试，防止同患者邻拍和重叠窗口泄漏；**201 和 202 来自同一受试者，必须进入同一分区**。不能将传统记录列表直接当作保证患者独立的列表。当前不作随机心拍级划分。标准化参数只能在训练集拟合；类别权重/重采样/增强仅用于训练分区。评估需给出每类召回率、精确率、F1、混淆矩阵及宏平均，不能只看总体准确率；缺失类别、不同记录和导联差异、质量差异都应单独报告。

## 可复现性、输出与限制

环境：Python {platform.python_version()}；""" + ", ".join(f"{m} {version(m)}" for m in ("wfdb", "numpy", "pandas", "matplotlib")) + f"""。完整环境版本见 `results/environment.json` 与 `requirements-lock.txt`。运行配置见 `results/run_config.json`，输出校验见 `results/verification.json`。程序支持 `--records all` 扩展官方 48 记录列表（本次没有运行全库）。

共有 {len(figure_table)} 张本轮图片，精确范围见 `results/figure_manifest.csv`；示例心拍及原始样本边界见 `results/plotted_beats.csv`。所有 CSV 使用 UTF-8 BOM，便于 Windows Excel 打开；含原始字符串字段的 CSV 应以文本方式导入，尤其注意 `+`、`=` 等原始符号。相对时间不是患者绝对测量日期。

本报告只讨论当前子集；稀有类覆盖不足、质量代理非临床指标、专家标注未作独立复核，均是已知限制。开发助手的视觉观察保存在 `reports/visual_review.json`，仅在全部原始文件 SHA256 及窗口参数匹配时自动纳入，避免扩展记录后套用旧结论。未解决的目录权限或交付问题以最终执行说明为准。

## 本轮图片索引

"""
    for row in figure_table.itertuples():
        name = row.file.split("/")[-1]
        text += f"\n- [{name}](../{row.file}) — {row.scope}\n"
    (root / "reports" / "data_exploration.md").write_text(text, encoding="utf-8")
