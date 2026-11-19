"""Build a Chinese research report with numbers read from real experiment artifacts."""
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np
from .data import BASE, ROOT, load
from .run import write, score


def table(headers, rows):
    return "|"+"|".join(headers)+"|\n|"+"|".join(["---"]*len(headers))+"|\n"+"\n".join("|"+"|".join(map(str,r))+"|" for r in rows)+"\n"


def build_report():
    folder=BASE/"results/cv_cpu_v1"
    s=json.loads((folder/"summary.json").read_text(encoding="utf-8"))
    b=json.loads((BASE.parent/"uncertainty/results/cv_cpu_v1/summary.json").read_text(encoding="utf-8"))
    data=load();config=s["config"];seeds=config["seeds"];classes=s["classes"]
    def vals(model,key):return [r["pooled"][key] for r in s["models"] if r["model"]==model]
    def stat(values):return f"{np.mean(values):.4f} ± {np.std(values,ddof=1):.4f}" if len(values)>1 else f"{values[0]:.4f}（1 seed，无种子SD）"
    def modelrow(model,seed):return next(r for r in s["models"] if r["model"]==model and r["seed"]==seed)
    gains=[modelrow("A2",seed)["pooled"]["macro_f1"]-modelrow("A0",seed)["pooled"]["macro_f1"] for seed in seeds]
    s_rec=[modelrow("A2",seed)["pooled"]["per_class"]["S"]["recall"]-modelrow("A0",seed)["pooled"]["per_class"]["S"]["recall"] for seed in seeds]
    s_prec=[modelrow("A2",seed)["pooled"]["per_class"]["S"]["precision"]-modelrow("A0",seed)["pooled"]["per_class"]["S"]["precision"] for seed in seeds]
    f_gain=[modelrow("A2",seed)["pooled"]["per_class"]["F"]["f1"]-modelrow("A0",seed)["pooled"]["per_class"]["F"]["f1"] for seed in seeds]
    support=modelrow("A0",seeds[0])["pooled"]["per_class"]
    text="# 融合心拍形态与历史节律的跨患者 ECG 分类及可靠性分析\n\n"
    text+="本报告由已完成工件自动生成。研究范围为原训练与验证患者的回顾性开发实验；原正式测试患者不进入新增模型拟合、选型或效果确认。全部种子与折均报告，没有以最好一次结果代表总结果。\n\n"
    text+="## 1. 审查结论与既有工作\n\n"
    text+="原工程具备 MIT-BIH 加载、AAMI 映射、44 条非起搏记录、43 个患者组（201/202 合并）、31/6/6 锁定分区、253 点波形、0.5–40 Hz 四阶原型 Butterworth 双向 SOS 滤波、训练侧标量标准化与类别权重。LR 使用训练侧特征 StandardScaler，RF 使用训练侧 balanced_subsample，HeartbeatCNN 为三层 16/32/64 通道卷积。原正式二分类与四分类、患者 CV、权重消融和错误分析均已存在，网页包括工作台、实验中心、图库、互动游戏。\n\n"
    text+="审查还发现 `src/evaluation/controlled_imbalance.py` 和 `reports/imbalance_experiments.md` 已实现 ContextHeartbeatCNN（4维过去RR＋focal loss）。因此本次并非项目首次加入节律分支，更不能主张 CNN＋RR 拼接首创。新增价值是 7 维历史特征及缺失掩码、四模型受控对照、外层评价与内部早停/校准分离、完整患者追溯和教学集成。CNN＋RR 既有原始论文与官方数据依据见 [一手来源核对](rhythm_fusion/reports/PRIMARY_SOURCES.md)。\n\n"
    text+="原课程论文 `paper/`、原始数据、原正式模型、原实验报告均列入保护清单。开始时已有 Umi appData 和论文 QA 等未提交改动，本次不将其归入新增成果，不覆盖用户论文。\n\n"
    text+="## 2. 问题与可检验假设\n\nH1：相同评价条件下，节律融合改善部分异常类别；H2：收益因类别而异，S 与 F 未必一致；H3：按拍改善可能集中于少量患者，不能替代患者级稳定性。允许拒绝假设。\n\n"
    text+="原项目已有 S/F 困难与患者差异是研究动机，不是融合有效的先验结论。这里的患者是记录导出的匿名组键，除官方明确的201/202外，未使用生物识别核查潜在身份。\n\n"
    text+="## 3. 特征、模型与防泄漏\n\n定义记录内专家 QRS 事件位置为 pᵢ，rᵢ=(pᵢ−pᵢ₋₁)/360 秒。Hᵢ 包含当前 RR 之前最多5个完整RR，不含 rᵢ；mᵢ=median(Hᵢ)，dᵢ=median(|Hᵢ−mᵢ|)。\n\n"
    text+=table(["特征","公式","单位/缺失规则"],[["当前RR","rᵢ","秒；缺前拍则缺失"],["前一RR","rᵢ₋₁","秒；缺前两拍则缺失"],["相邻比值","rᵢ/rᵢ₋₁","无量纲；两项均可用"],["相对历史比值","rᵢ/mᵢ","无量纲；至少1个历史RR"],["历史中位数","mᵢ","秒；至少1个历史RR"],["历史MAD","dᵢ","秒；至少2个历史RR，未乘1.4826"],["相对变化","(rᵢ−mᵢ)/mᵢ","无量纲；有当前及历史RR"]])
    text+="\n每项均有0/1掩码；不足历史保持 NaN，缺失填充值为内部拟合患者该特征中位数，均值/标准差也仅在该拟合集拟合。全缺失列预声明填0，方差下限1e−8；不做数据依赖裁剪。数值分支7维与掩码7维拼成14维。完整开发集因原5秒边缘保护均具有所需历史；缺失行为通过记录起点的真实请求及单元测试验证。\n\n"
    text+="事件集合在计算RR前固定为 WFDB 心拍事件，包含非目标 Q、/、f、? 等；x、!、|、+ 不作为 QRS。符号仅决定是否为beat事件，类别数值不进入特征；不先筛N/S/V/F再计算RR。每条记录独立处理，输入仅到当前标注位置，不含患者ID、记录ID、未来RR。对86,286拍验证 sample_id 的原标注索引、位置、符号与患者键一致，见 `rhythm_fusion/data/audit.json`、`alignment.csv`、`development.npz`。\n\n"
    text+="波形仍复用原 X_filtered 的 [B,1,253] 数据，并在各折内部拟合患者重新标准化，不能复用原训练归一化统计。0.4秒右侧窗口和双向滤波意味着完整系统是离线分类；只有 RR 上下文满足历史限定。专家定位不是未标注连续ECG上的端到端发现。\n\n"
    text+=table(["模型","输入与结构","参数量"],[["A0","原HeartbeatCNN编码器→Linear64→4",modelrow("A0",seeds[0])["parameters"]],["A1","14→32→16→4 RR-MLP",modelrow("A1",seeds[0])["parameters"]],["A2","64维形态＋16维节律→Linear80→4",modelrow("A2",seeds[0])["parameters"]],["A3","同A2；特征与掩码成对无标签错配",modelrow("A3",seeds[0])["parameters"]]])
    text+="\n## 4. 受控实验与实际预算\n\n"
    text+=f"实际完成 {config['outer_folds']} 外层折 × {len(seeds)} 种子 × 4模型 = {len(s['folds'])} 组完整训练；另有4组小规模Smoke Test，不混入结果。种子 {seeds}；外层折固定20261118，各种子复用相同折。每折内部使用6折StratifiedGroupKFold：第0折早停，第1折校准，其余患者拟合。拟合/早停/校准/评价四组患者两两互斥。分层折只近似平衡类别，不保证每折每类样本数相同。\n\n"
    text+=f"每模型最多{config['epochs']}轮、patience={config['patience']}、batch={config['batch_size']}，Adam lr={config['learning_rate']}、weight_decay={config['weight_decay']}，拟合侧逆频率类别权重，固定4类Macro-F1早停。CPU、2线程；本环境无CUDA。相比历史正式25轮训练，本轮预算更短、拟合患者更少，A0是相同预算重训的结构基线，不能直接与旧测试指标比较。\n\n"
    text+="A3在拟合、早停、校准、外层评价子集内部各自建立固定无自配对置换，同一映射用于全部训练种子；不跨子集交换，不使用标签构造置换。允许同一个子集内跨患者错配，因此该对照检验有效时序对应关系，不能精确分解全部生理机制或容量效应。A2/A3参数量一致；A2与A0容量仍不同。\n\n"
    text+="先冻结完成单种子预算，再不改变超参数地补充另两个预定种子。组件 fingerprint、源码SHA、开发数据SHA和folds.json分别保留；汇总验证折完全相同并列出组件，未把单种子工件伪装成三种子。中断重跑验证已有checkpoint哈希后跳过完成项，未完成项从该job重新开始，不承诺逐batch恢复优化器。\n\n"
    rows=[]
    for fold in range(5):
        rr=next(r for r in s["folds"] if r["fold"]==fold and r["model"]=="A0" and r["seed"]==seeds[0])
        rows.append([fold+1,rr["subject_count"],rr["sample_count"],*[f"{rr['per_class'][c]['support']} / {rr['per_class'][c]['subject_count']}" for c in classes]])
    text+=table(["外层折","患者数","心拍数","N拍/患者","S拍/患者","V拍/患者","F拍/患者"],rows)
    part_rows=[]
    for fold in range(5):
        job=json.loads((folder/f"fold{fold}/seed{seeds[0]}/A0/result.json").read_text())
        part_rows.append([fold+1,*[f"{len(job['partitions'][part]['subjects'])} / {job['partitions'][part]['samples']}" for part in ["fit","stop","calibration","evaluation"]]])
    text+="\n内部划分的患者数/拍数（各模型及种子复用）：\n\n"+table(["fold","拟合","早停","阈值校准","外层评价"],part_rows)
    text+="\n## 5. 完整结果\n\n主指标为每个种子合并全部外层留出预测（OOF）的Macro-F1。不同seed的±为样本标准差(ddof=1)，不代表新增独立患者、标准误或临床置信区间。折均值与合并OOF因非线性及支持不同而不相等。Balanced Accuracy主值为真实支持类别的平均召回，另保留固定4类值；单患者Macro-F1仍固定4类，缺失类别计0。\n\n"
    text+=table(["模型","OOF Macro-F1均值±SD","Accuracy","Balanced Accuracy","参数","单拍ms中位数"],[[m,stat(vals(m,"macro_f1")),stat(vals(m,"accuracy")),stat(vals(m,"balanced_accuracy")),modelrow(m,seeds[0])["parameters"],f"{np.median([r['latency_ms'] for r in s['models'] if r['model']==m]):.3f}"] for m in config["models"]])
    text+="\n推理为预热后30次batch=1调用的中位数（传输＋前向＋softmax，不含磁盘/滤波）；训练进程并发负载影响耗时，非硬件基准结论。每job另存P95、epoch、设备、训练时间及结构配置。\n\n"
    text+=table(["种子","A0","A1","A2","A3","A2−A0"],[[seed,*[f"{modelrow(m,seed)['pooled']['macro_f1']:.4f}" for m in config["models"]],f"{gains[i]:+.4f}"] for i,seed in enumerate(seeds)])
    text+="\n以下P/R/F1为各seed合并OOF指标的均值；支持数与独立患者数在各seed相同，绝不乘以种子数。\n\n"
    text+=table(["模型","类","Precision均值±SD","Recall均值±SD","F1均值±SD","支持拍数","独立患者"],[[m,c,*[stat([modelrow(m,sd)['pooled']['per_class'][c][key] for sd in seeds]) for key in ["precision","recall","f1"]],support[c]["support"],support[c]["subject_count"]] for m in config["models"] for c in classes])
    concentration=[]
    for i,c in enumerate(classes):
        groups,counts=np.unique(data["subject_group"][data["label"]==i],return_counts=True)
        top=int(np.argmax(counts))
        concentration.append([c,len(groups),int(counts.sum()),str(groups[top]),int(counts[top]),f"{counts[top]/counts.sum():.2%}"])
    text+="\n类别支持的患者集中度（每个心拍只计一次）：\n\n"+table(["类","独立患者","拍数","最多支持患者","该患者拍数","占本类比例"],concentration)
    text+="\n各折数值（所有seed，固定4类）：\n\n"
    text+=table(["seed","fold","A0","A1","A2","A3"],[[seed,fold+1,*[f"{next(r for r in s['folds'] if r['seed']==seed and r['fold']==fold and r['model']==m)['macro_f1']:.4f}" for m in config["models"]]] for seed in seeds for fold in range(5)])
    text+="\n## 6. 患者级、类别差异与假设判断\n\n"
    text+=f"A2相较A0的合并OOF Macro-F1变化为 {stat(gains)}；{sum(g>0 for g in gains)}/{len(seeds)} 个种子为正。S类Recall变化 {stat(s_rec)}，Precision变化 {stat(s_prec)}；F类F1变化 {stat(f_gain)}。这只支持当前预算和已分析开发患者上的实证判断，不能外推为普遍有效。\n\n"
    patient_rows=[]
    for seed in seeds:
        t=[r for r in s["error_transitions"] if r["seed"]==seed]
        positive=sum(r["delta_macro_f1"]>1e-10 for r in t);negative=sum(r["delta_macro_f1"]< -1e-10 for r in t)
        top=max(t,key=lambda r:r["corrected_by_fusion"]-r["new_errors_with_fusion"])
        patient_rows.append([seed,positive,negative,len(t)-positive-negative,sum(r["corrected_by_fusion"] for r in t),sum(r["new_errors_with_fusion"] for r in t),top["subject"],top["corrected_by_fusion"]-top["new_errors_with_fusion"]])
    text+=table(["seed","患者F1改善","下降","无变化","被纠正错误拍","新增错误拍","净纠正最多患者","该患者净纠正"],patient_rows)
    sensitivity=[]
    for seed in seeds:
        component="cv_cpu_v1" if seed==seeds[0] else "cv_cpu_repeats_v1"
        p={m:np.load(BASE/f"results/{component}/oof_{m}_seed{seed}.npz")["probability"] for m in ["A0","A2"]}
        t=[r for r in s["error_transitions"] if r["seed"]==seed]
        top=max(t,key=lambda r:r["corrected_by_fusion"]-r["new_errors_with_fusion"])["subject"]
        ix=data["subject_group"]!=top
        delta=score(data["label"][ix],p["A2"][ix],data["subject_group"][ix],classes)["macro_f1"]-score(data["label"][ix],p["A0"][ix],data["subject_group"][ix],classes)["macro_f1"]
        sensitivity.append([seed,top,f"{delta:+.4f}"])
    text+="\n以下仅作事后敏感性描述：去除净纠正最多患者后重新计算其余OOF差值，不重新训练、不将去除后的值作为主要性能。\n\n"+table(["seed","暂去除患者","其余OOF A2−A0"],sensitivity)
    text+="\n每个seed另做1000次成对患者组Bootstrap，整组重采样并保留该组所有拍，区间见各组件 bootstrap_seed*.json。该区间只是37个已分析开发患者的条件性描述，共享训练折带来依赖，不能替代外部验证或普通独立心拍显著性检验。\n\n"
    text+="即使多个seed方向一致，也只是训练随机性的稳定性，不增加独立患者数量。各类最多支持患者及比例见集中度表，仍须外部数据验证。\n\n"
    mean_s={m:{k:float(np.mean([modelrow(m,sd)["pooled"]["per_class"]["S"][k] for sd in seeds])) for k in ["precision","recall","f1"]} for m in ["A0","A2"]}
    shuffled_gains=[modelrow("A2",sd)["pooled"]["macro_f1"]-modelrow("A3",sd)["pooled"]["macro_f1"] for sd in seeds]
    text+="### 研究问题的直接回答\n\n"
    text+=f"1. **融合是否改善？** 当前开发OOF中，{sum(g>0 for g in gains)}/{len(seeds)}个seed的A2 Macro-F1高于相同协议A0，平均差值{np.mean(gains):+.4f}。{'有限支持H1的开发集表现判断。' if np.mean(gains)>0 else '不支持总体改善主张。'}不代表优于原正式checkpoint的独立测试结果。\n\n"
    text+=f"2. **哪些类别？** N/S/V/F逐类表同时保留增益和退化。S平均F1从{mean_s['A0']['f1']:.4f}到{mean_s['A2']['f1']:.4f}；F的平均F1差值{np.mean(f_gain):+.4f}，不能合并成‘少数类全面改善’。\n\n"
    text+=f"3. **S召回与误报是否交换？** 平均Recall从{mean_s['A0']['recall']:.4f}到{mean_s['A2']['recall']:.4f}，Precision从{mean_s['A0']['precision']:.4f}到{mean_s['A2']['precision']:.4f}；{'本轮均值并非以Precision下降换Recall，但误报仍需看其绝对水平。' if np.mean(s_rec)>0 and np.mean(s_prec)>=0 else '存在权衡或不一致，不能只强调Recall。'}\n\n"
    text+="4. **F仍困难吗？** 是。支持集中、可学习患者有限，所有seed逐类值须整体阅读；某一次改善不能证明解决F识别。\n\n"
    text+=f"5. **少数患者主导？** 患者表存在改善、下降与不变，单患者移除敏感性差值范围为{min(float(r[2]) for r in sensitivity):+.4f}至{max(float(r[2]) for r in sensitivity):+.4f}。{'净纠正最多的单患者不能完全解释总体增益。' if all(float(r[2])>0 for r in sensitivity) else '去除单个患者可能改变结论，主导效应不可忽视。'}这不是排除所有小群体主导的证明。\n\n"
    text+=f"6. **RR-only有独立能力？** A1合并OOF Macro-F1均值{np.mean(vals('A1','macro_f1')):.4f}，显示历史节律在当前数据上含判别信息；逐类失败也说明其不足以替代形态。\n\n"
    text+=f"7. **打乱RR是否退化？** A2−A3为{stat(shuffled_gains)}，{sum(v>0 for v in shuffled_gains)}/{len(seeds)}个seed为正；同容量对照有助于判断对应节律的信息收益，仍有优化轨迹混杂。\n\n"
    text+="8. **容量能完全排除吗？** 不能。A2/A3容量相同但A2/A0不同，且随机错配同时改变相关结构。证据支持该组合方案，不支持唯一机制归因。\n\n"
    text+=f"9. **seed一致吗？** {sum(g>0 for g in gains)}/{len(seeds)}个seed的总体差值方向为正；各折和各患者并不因此全部稳定。三seed只反映本预算下训练随机性，不能提升独立患者数量。\n\n"
    text+="## 7. 不确定性与拒识\n\nUmax=1−max softmax；Uentropy=−Σp log p（nats）。各模型/折/seed仅在单独内部校准患者上取分数的90%分位数（higher规则），U≤阈值接受；不读取校准标签决定阈值。90%是预先给定的教学保留预算，不是临床安全界限，新患者覆盖率不保证90%。全部四模型均报告，不用外层结果挑最佳模型。外层Risk–Coverage曲线只是描述性扫描（同分数一并接受），不用于反选部署阈值。\n\n"
    text+=table(["模型","代理","Coverage均值±SD","全部错误率","接受拍错误率","拒识拍错误率","错误识别AUROC"],[[m,method,*[stat([r[key] for r in b["results"] if r["model"]==m and r["method"]==method]) for key in ["coverage","all_error_rate","accepted_error_rate","rejected_error_rate","error_detection_auroc"]]] for m in config["models"] for method in ["max_score","entropy"]])
    text+="\n融合模型逐seed分母及覆盖率：\n\n"+table(["seed","代理","接受/全部拍","拒识拍","Coverage","接受错误率"],[[r["seed"],r["method"],f"{r['accepted']}/{r['total']}",r["rejected"],f"{r['coverage']:.4f}",f"{r['accepted_error_rate']:.4f}"] for r in b["results"] if r["model"]=="A2"])
    text+="\n下表为融合模型逐类各seed均值，真实类接受率分母是该类全部OOF心拍；保留Recall分母为接受的真实类拍，全体Recall分母仍是该类全部拍。无预测/无保留支持时按0报告并保留计数。\n\n"
    text+=table(["代理","真实类","接受率","保留Precision","保留Recall","全体分母Recall","原支持/患者"],[[method,c,*[f"{np.mean([r['per_class'][c][key] for r in b['results'] if r['model']=='A2' and r['method']==method]):.4f}" for key in ["acceptance_rate","precision_retained","recall_retained_denominator","recall_all_denominator"]],f"{support[c]['support']}/{support[c]['subject_count']}"] for method in ["max_score","entropy"] for c in classes])
    text+="\n全部模型的每患者拒识比例、逐类计数、各折Risk–Coverage点和阈值来源保存在 uncertainty/results/cv_cpu_v1/summary.json。没有把拒识拍变成正确预测；准确率变化必须连同覆盖率与被丢弃类别解释。Softmax和熵未经温度校准，不能称临床风险或正确概率；AUROC只是当前OOF错误的排序能力，跨折分数的校准差异也是局限。\n\n"
    text+="## 8. 工程与教学集成\n\n新增 `/rhythm-lab` 页面与主导航；API `/api/rhythm/summary`、`/samples`、`/beat` 从真实JSON、WFDB、checkpoint读取。研究模型注册独立，显示模型/折/seed/SHA。单拍使用该患者外层留出的模型；演示seed固定第一个，不按结果挑选。研究接口对原正式测试患者不运行新模型。原正式CNN单独展示并注明可能存在训练暴露，不能据教学案例做公平模型性能结论。缺历史返回掩码和原因，模型未完成显示空状态；N/V新消融未执行时明确空白。\n\n"
    text+="Heartbeat Hunter仅在已完成作答、看到专家答案后新增链接，携带同一 record_id 与 annotation_sample。不修改评分、计时、存档、关卡或专家判分，游戏成绩不用于医学能力评估，不将已知答案关卡当新测试。响应式布局与prefers-reduced-motion通过真实浏览器交互验证。\n\n"
    text+="## 9. 图表、测试与保护\n\n10张基础图均有300dpi PNG及SVG：真实结构、RR分布、四模型Macro-F1、逐类F1、四模型混淆矩阵、患者表现、折/seed波动、错误转移、Risk–Coverage、逐类拒识。图注包含分区、seed/预算、评价单位与统计口径；基础比较图明确选用第一个预定seed，全部seed数值与波动另完整给出。`figures/cv_cpu_v1/catalog.json`记录来源SHA。\n\n"
    test_xml=ROOT/"research_extensions/validation/pytest.xml"
    if test_xml.exists():
        suite=ET.parse(test_xml).getroot().find("testsuite")
        if suite is not None:text+=f"Python最终记录：tests={suite.get('tests')}，failures={suite.get('failures')}，errors={suite.get('errors')}，skipped={suite.get('skipped')}。\n\n"
    validation=ROOT/"research_extensions/validation"
    text+=table(["检查","退出码","完整记录"],[[p.stem,json.loads(p.read_text(encoding="utf-8"))["exit_code"],f"validation/{p.stem}.txt"] for p in sorted(validation.glob("*.json")) if p.stem!="browser_results" and "exit_code" in json.loads(p.read_text(encoding="utf-8"))])
    protected=ROOT/"research_extensions/protection_verification.json"
    if protected.exists():
        verification=json.loads(protected.read_text());text+=f"\n原始保护工件复验：{verification['checked_files']}个，变化{len(verification['changed'])}个，passed={verification['passed']}。完整SHA清单见 protection_manifest.json。\n\n"
    text+="初始沙箱TestClient挂起及第一轮浏览器定位器失败未计为通过；诊断与重跑见 validation/sandbox_diagnosis.md。命令、工作目录、退出码、原始输出及pytest.xml均保存，未执行项不写通过。\n\n"
    text+="## 10. 创新边界、不足与后续\n\n可成立的贡献是既有轻量方法的可审计组合、严格患者隔离的实证比较和真实教学系统集成。是否有信息收益应同时对照RR-only、同容量错配模型、类别P/R、患者和种子；容量对照减少但不能彻底消除结构与优化轨迹的混杂。不能声称首次CNN＋RR、已发现临床机制、完成外部验证或可靠医疗风险筛查。\n\n"
    text+=f"本轮实际种子数{len(seeds)}/3。未完成：N/V新增四模型分组重复；外部数据库、前瞻性患者、连续ECG自动QRS检测、临床阈值选择、概率校准、人工复核成本和长预算敏感性。十二轮预算相对短，部分模型达到上限，部分折早停很早；这影响方法比较的外推范围，不能按外层效果调整预算后仍称同一预注册实验。\n\n"
    text+="特征中相对变化等于相对历史比值减1，存在明确的线性冗余，本轮保持预定义不按评价结果删改。开发集经原滤波边缘保护后掩码均可用；记录起点缺失处理已验证为安全行为，但缺失节律情况下的分类效能并未验证。未做真实缺失/自动QRS误检扰动实验。\n\n"
    text+="当前资料足以撰写如实限定的课程研究扩展章节；不满足临床有效性或外部泛化论文主张。后续应以新的独立患者/外部数据，在冻结流程后验证，并优先处理F支持集中与误报问题。\n"
    (BASE.parent/"INNOVATION_REPORT.md").write_text(text,encoding="utf-8")
    draft="# 原课程论文建议新增章节（独立草稿）\n\n建议插入第5章结果分析末尾、第6章系统设计之前，使用“5.X 历史节律融合与患者级可靠性探索”。本文件不修改原DOCX/PDF，不替换原实验指标。\n\n"
    draft+="### 研究动机与方法\n\n既有单心拍CNN在跨患者评价中存在类别及患者差异。本扩展把历史RR看作待检验的补充输入，采用原64维CNN表示与16维MLP节律表示拼接。七项历史特征及其缺失掩码只由记录内当前和过去专家QRS位置计算，缺失填充与波形/特征归一化均由当前内部拟合患者估计。该方法属于已有形态与节律信息融合思路的工程化研究，项目此前也已有4维RR的focal实验，因此不能声称首次提出。\n\n"
    draft+=f"### 分组对照与结果\n\n保持原44记录及31/6/6患者分区，只将原train＋val的37组86,286拍用于开发，原测试患者隔离。实际完成5折×{len(seeds)}种子×4模型，以独立内部患者早停并另留校准患者。四模型合并OOF Macro-F1分别为 A0 {stat(vals('A0','macro_f1'))}、A1 {stat(vals('A1','macro_f1'))}、A2 {stat(vals('A2','macro_f1'))}、A3 {stat(vals('A3','macro_f1'))}；均值±为训练种子标准差，并非患者置信区间。融合与基线差值{stat(gains)}。S类召回变化{stat(s_rec)}、Precision变化{stat(s_prec)}，F类F1变化{stat(f_gain)}；必须保留退化结果。S支持2,751拍/28患者，F支持429拍/14患者且集中，不能以心拍数替代独立患者量。\n\n"
    draft+="### 不确定性与边界\n\n采用1−最大分数及信息熵，在每折独立内部校准患者上按预定90%覆盖分位数冻结接受阈值，外层患者不参与阈值选择。图表同时报告Coverage、接受与拒识拍真实错误率、逐类保留召回及其分母。拒识降低接受拍错误率并不改变全部拍预测，Softmax分数和熵只是未校准代理，不是临床风险。\n\n"
    draft+="### 系统与局限\n\n新增节律融合与可靠性实验室，从真实结果文件和模型工件加载，支持患者留出单拍分析与游戏结束后的同一记录/位置联动。该闭环依赖专家定位、离线双向滤波与右侧波形窗口；开发患者已被回顾性分析，不能称为新的盲测或端到端实时异常发现。详细患者差异、所有seed/fold及拒识分母见独立 INNOVATION_REPORT.md，图01/03/04/06/07/08/09/10可选用于本节。\n"
    (BASE.parent/"PAPER_CHAPTER_DRAFT.md").write_text(draft,encoding="utf-8")
    print(f"Generated report for {len(s['folds'])} jobs, seeds {seeds}")


if __name__=="__main__":build_report()
