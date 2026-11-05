"""Explain every generated figure using its computed evidence and declared scope."""
import json
from .report import markdown_table
from .visuals.common import FAMILIES


def generate_report(root,book,annotations,beats,tables,config,manifest):
    catalog=tables['figure_catalog']; counts=tables['aami_counts']
    category_names={'A':'数据分布','B':'原始波形','C':'单心拍形态','D':'节律分析','E':'数据质量','F':'降维探索'}
    nonbeat=int((annotations.annotation_kind=='non_beat').sum())
    mapped=int(counts['count'].sum())
    valid=int((beats.extraction_status=='valid').sum())
    visual_notes={}
    review_path=root/'reports/visualization_review.json'
    if review_path.exists():
        review=json.loads(review_path.read_text(encoding='utf-8'))
        hashes={r['file']:r['sha256'] for r in manifest if r['file'].endswith(('.dat','.hea','.atr'))}
        signature={k:config[k] for k in ('records','pre_s','post_s','seed','embedding_max','embedding_per_stratum','perplexities')}
        if review.get('raw_sha256')==hashes and review.get('configuration')==signature:
            visual_notes=review.get('figure_notes',{})
    distribution='\n'.join(f'| {code} | {category_names[code]} | {int((catalog.category==code).sum())} | `figures/{folder}/` |' for code,folder in FAMILIES.items())
    ranking=tables['non_n_record_ranking'].sort_values('non_n_percentage',ascending=False)
    first,last=ranking.iloc[0],ranking.iloc[-1]
    rr_notes='；'.join(f"{row.record}: 平均 RR {row.mean_rr_s:.4f} s，SD {row.std_rr_s:.4f} s" for row in tables['rr_statistics'].head(6).itertuples())
    template_notes=[]
    for lead,part in tables['template_correlations'].groupby('lead'):
        pair=part[(part.class_row=='N')&(part.class_column=='S')].correlation
        if len(pair) and pair.notna().iloc[0]: template_notes.append(f'{lead} 的 N/S 类均值模板相关系数 r={pair.iloc[0]:.4f}')
    highest_std=tables['signal_quality'].loc[tables['signal_quality']['std'].idxmax()]
    talking_points=(f"- 非 N 组比例最高为记录 {first['record']}（{first.non_n_percentage:.3f}%），最低为记录 {last['record']}（{last.non_n_percentage:.3f}%），记录间构成差异不能被合并频率替代。\n"
                    f"- {rr_notes}。这是全部已识别心拍的 RR 描述量，不是正常 NN 的临床 HRV。\n"
                    f"- {'；'.join(template_notes) or 'N/S 中存在缺失模板，不能计算两类模板相关。'}；相关值只描述类均值，不能替代逐拍区分能力。\n"
                    f"- 整条信号标准差最高的是 {highest_std['record']}/{highest_std.lead}（{highest_std['std']:.4f} {highest_std.unit}）；这只提供复核线索，不是噪声率。\n")
    text=f'''# MIT-BIH 心电图可视化图集与逐图分析

本轮仅做数据探索与可视化，**没有训练深度模型或分类器，也没有进行训练/验证/测试划分**。记录：**{', '.join(config['records'])}**；数据库版本 1.0.0；输出 {len(catalog)} 张 300 dpi PNG，分为下列六类。所有数字来自本轮代码计算。

| 代码 | 图集类别 | 本轮张数 | 目录 |
| --- | --- | --- | --- |
{distribution}

## 范围与主要统计事实

- 总标注 {len(annotations)} 条，其中已映射心拍 {mapped}、非心拍 {nonbeat}；其余 {len(annotations)-mapped-nonbeat} 条明确保留为未映射/未知项，不猜测类别。
- 已识别心拍 {len(beats)} 个，其中 {valid} 个完整、有限且已映射的主导联窗口用于形态和降维；其余 {len(beats)-valid} 个仍保留在原始统计与审计表中。
- 全部形态图按**相同导联名称**分组，优先 MLII，没有 MLII 的记录使用其实际首导联，并独立汇总，不将 MLII 与 V5 等直接混合。
- 本轮没有分析全部 48 条记录。`--records all` 可扩展，但需要另行运行；当前类频率不能当作全库或临床人群患病率。

{markdown_table(counts)}

完整原始符号表（含非心拍）如下。中文含义和五类映射均沿用既有显式规则；本轮未更改专家标签。

{markdown_table(tables['raw_symbol_counts'])}

## 可用于课程汇报的计算结果

{talking_points}

## 计算方法与读图约定

1. **数据与标签**：使用 PhysioNet 官方 `.dat/.hea/.atr`，逐文件校验 SHA256、逐导联核对数字校验和并检查标注范围。原始 `symbol` 与 `aami_group` 分开保存。N←N,L,R,e,j；S←A,a,J,S；V←V,E；F←F；Q←/,f,Q。节律、质量与伪迹符号不计作心拍。[数据库说明](https://physionet.org/content/mitdb/1.0.0/)、[原始符号定义](https://physionet.org/static/lightwave/doc/annotations.html)、[AAMI 映射文献](https://doi.org/10.1109/TBME.2004.827359)。
2. **“异常比例”的操作性定义**：排序图计算 `(S+V+F+Q)/(N+S+V+F+Q)`，图中明确标为“非 N 组比例”。N 组包含束支阻滞和部分逸搏，Q 包含起搏/无法分类；这个比值不能当作严格的医学异常率。
3. **窗口**：原始专家标注前 {config['pre_s']} s、后 {config['post_s']} s；包含中心和末采样点，stop 列为右开端点。360 Hz、默认参数时为 253 点。越界只影响片段，不删原始心拍计数；没有重新定位 R 峰，也没有滤波或改写原始数据。窗口可能包含相邻心拍。
4. **随机与代表性示例**：随机种子 {config['seed']}，每类最多 20 拍、不放回；不足时全部展示，零样本只显示缺失说明。网格首先取减中位数后最接近类均值的真实片段，再取不同峰峰值排序位置的真实片段；每格标注记录、导联、原始样本和秒数。抽样与网格的精确标识均见 `plotted_heartbeat_windows.csv`。
5. **形态与能量**：左侧原始幅值保持物理单位；减窗口中位数的版本仅用于控制常量基线。峰峰值、最大/最小值描述整个窗口，不是专家分割的 QRS 指标。窗口能量定义为 `sum(x**2)/fs`，单位 mV²·s，另报告减中位数后的能量。箱线图须为 1.5 IQR；均值波形阴影为逐点 ±1 标准差，不是置信区间。
6. **RR**：仅从同一记录连续专家心拍标注计算，不跨记录，不将非心拍事件当作 RR 邻居。RR 分析使用全部已识别心拍，与形态窗口是否越界无关；散点按当前拍类别着色。包含异位心拍的 RR 不等于正常 NN 间期，不进行临床 HRV 诊断。
7. **质量**：振幅/标准差是描述量；1 s 块中位数在 10 s 内的变化是漂移候选代理，≥0.5 mV 只作示例选择规则，也可能由宽心拍、突变伪迹等造成。专家 `~` 是质量改变事件，不是确定的噪声持续时长。未触及 ADC 轨值也不说明没有严重干扰。
8. **PCA/t-SNE**：所有有效同导联窗口先减各窗中位数；第二版本另除以各窗 RMS，去掉幅值尺度（常量窗口不除以零）。PCA 使用全部有效窗口且不按采样点做方差标准化。t-SNE 先按记录×类别各限 {config['embedding_per_stratum']} 拍，再等额分配至总上限 {config['embedding_max']}，均为固定种子不放回；保留小样本层，不复制稀有类。对入选矩阵先 PCA 到最多 50 维，再运行 t-SNE，perplexity={config['perplexities']}、init=pca、learning_rate=auto、最多 1000 轮。每个投影同时按类别和记录着色，以检查记录效应。t-SNE 抽样图不代表原始类频率，坐标和簇间距离不能直接比较；其 KL 也不是分类准确率。[PCA 官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html)、[t-SNE 官方文档](https://scikit-learn.org/stable/modules/generated/sklearn.manifold.TSNE.html)。

## 后续建模分析应注意

当前 F 可能极少、Q 可能缺失，因此不能据这两条记录评价完整五分类能力。类均值可能掩盖多形态或受大记录支配；二维聚集不等于真实可分性，也不是模型验证。未来划分须按受试者独立，**201 和 202 来自同一受试者，必须在同一分区**；不要随机心拍级划分或让重叠窗口跨分区。未来标准化与降维若用于预测管线，只能在训练分区拟合，验证/测试单独变换；本轮所有数据上的探索性投影不可当作测试性能。

## 可复现入口与明细

```powershell
.\\.venv\\Scripts\\python.exe -m src.visualize --records 100 200 --offline
```

主入口 `src/visualize.py`；加载复用 `src/io.py`、下载复用 `src/download.py`、映射复用 `src/labels.py`；心拍截取与描述量位于 `src/heartbeat.py`；六类绘图模块位于 `src/visuals/`；本报告由 `src/visualization_report.py` 生成。

本轮清单与统计位于 `results/visualization/`：`figure_catalog.csv` 是全部图的解释索引；`all_beat_metadata.csv` 记录边界和 RR；`heartbeat_features.csv` 记录有效片段描述量；`embedding_coordinates.csv` 保存每个降维点的记录、原始标注位置和类别；`embedding_parameters.csv` 保存 t-SNE 参数；`template_correlations.csv` 保留缺失模板为 NA。每次运行以本轮清单为准，不自动删除其他运行留下的图片。

环境、配置和原始文件哈希见 `environment.json`、`run_config.json`、`download_manifest.csv`，完整性验证见 `verification.json`。各图下方的“计算结果”来自代码；额外“视觉核查”只来自开发助手对实际图像的查看，绑定本轮原始数据哈希及配置，未经额外心电专家复核，不能替代专家诊断。

## 逐图解释

'''
    for code in FAMILIES:
        text+=f'\n### {code}. {category_names[code]}\n\n'
        for entry in book.entries:
            if entry['category']!=code: continue
            text+=f"#### {entry['figure_id']} · {entry['title']}\n\n"
            text+=f"![{entry['figure_id']}]({('../'+entry['file'])})\n\n"
            text+=f"**读图目的**：{entry['purpose']}\n\n**计算结果**：{entry['computed_findings']}\n\n"
            note=visual_notes.get(entry['file'])
            if note: text+=f'**实际视觉核查**：{note}\n\n'
            text+=f"**解释边界**：{entry['interpretation_limits']}\n\n**数据范围**：`{entry['scope']}`\n\n"
    (root/'reports/visualization_summary.md').write_text(text,encoding='utf-8')
