"""Apply review-scoped additions to a copy of the V1 manuscript."""
from pathlib import Path
import re,json,csv,shutil
P=Path(__file__).resolve().parents[1]; ROOT=P.parent
source=P/'review/backup_v1/ECG_AI_课程论文初稿.md'
s=source.read_text(encoding='utf-8')
s=re.sub(r'表(\d+)',lambda m:'表{old'+m[1]+'}',s)
s=re.sub(r'图(\d+)',lambda m:'图{old'+m[1]+'}',s)
related=(P/'draft/v2_related_work.md').read_text(encoding='utf-8').split('<!--')[0].strip()
related=related.replace('表1','表{lit}')
s=re.sub(r'## 1\.2 .*?(?=## 1\.3)',related+'\n\n',s,flags=re.S)
s=s.replace('N L R e j','N、L、R、e、j').replace('A a J S','A、a、J、S').replace('| V E |','| V、E |').replace('| / f Q |','| /、f、Q |')
flow='''
表{flow} 数据构建的记录与心拍数量流程

| 构建阶段 | 记录范围 | 数量与单位 | 统计含义 |
|---|---|---|---|
| 原始记录与保留记录 | 全库→正式实验 | 48→44条；保留43受试者组 | 排除102、104、107、217；201/202同组 |
| 全部原始注释事件 | 48条 / 44条 | 112647 / 103724条 | 包含节律、质量等非心拍事件 |
| 显式AAMI映射覆盖心拍 | 48条 / 44条 | 109494 / 100733拍 | 仅N/S/V/F/Q映射符号，不等于注释事件总数 |
| N/V目标心拍 | 44条 | 97134拍 | 窗口技术排除前 |
| N/V有效窗口 | 44条 | 96554拍 | 排除540拍保护区与40拍边界不足 |
| N/S/V/F目标心拍 | 44条 | 100718拍 | 未纳入Q，窗口技术排除前 |
| N/S/V/F有效窗口 | 44条 | 100115拍 | 排除562拍保护区与41拍边界不足 |

表{flow}区分注释事件、映射心拍和有效窗口，所有数量均由原始符号统计、逐拍元数据及校验文件交叉核对。每个有效心拍对应一个253点窗口，不能将253个采样点计作253个独立训练样本。预处理先对连续信号实施固定滤波，再围绕标注截窗；患者划分后仅用训练窗口拟合归一化和损失权重。固定滤波不利用标签拟合，训练侧统计参数则不能从验证或测试侧估计。
'''
s=s.replace('## 2.3 信号预处理',flow+'\n## 2.3 信号预处理')
s=s.replace('## 3.1 逻辑回归','''模型选择分别覆盖线性基线、非线性树集成和局部时序卷积三种建模方式。它们使用相同任务分区和253点输入，但归纳偏置、损失权重及训练机制不同。因此该比较回答当前输入条件下哪种方案表现更好，不用于把所有差异归因于单个网络组件。

## 3.1 逻辑回归''')
training='''
表{train} 正式模型训练与选择条件

| 项目 | LR | RF | 1D-CNN |
|---|---|---|---|
| 主要规模参数 | C=1；最大迭代1000 | 100棵树；深度18 | 三层卷积；通道16/32/64 |
| 输入与缩放 | 253维；训练侧逐特征缩放 | 253维；全局标量标准化 | 单通道253点；全局标量标准化 |
| 类别处理 | balanced | balanced_subsample | 训练集逆频率交叉熵 |
| 优化设置 | lbfgs；容差0.001 | 叶节点最少2；抽样比例0.8 | Adam；lr=0.001；batch=256 |
| 选择与随机性 | 固定配置；seed=20261027 | 固定配置；同一seed | 最多25轮；patience=5；同一seed |
| CNN最佳轮次 | 不适用 | 不适用 | N/V第12轮；四分类第11轮 |

表{train}中的正式配置与权重探索实验分开记录。CNN输出logits直接送入交叉熵，推理时才转换为softmax分数；测试结果不参与检查点选择。两层最大池化分别缩短时间维，最后的自适应平均池化将每个通道聚合为一个数值，故线性分类器仅接收64维表示。
'''
s=s.replace('# 第四章',training+'\n# 第四章')
exp='''
表{exp} 各实验的设置与证据范围

| 实验 | 分类任务 | 模型 | 数据范围 | 主要指标 | 目的 |
|---|---|---|---|---|---|
| 固定测试主实验 | N/V | LR RF CNN | 固定31/6/6患者分区 | Accuracy 逐类P/R/F1 Macro-F1 | 比较两组心拍识别 |
| 固定测试扩展 | N/S/V/F | LR RF CNN | 同一患者分区 | 同上及混淆方向 | 观察任务扩展的变化 |
| 类别权重探索 | N/S/V/F | CNN四策略；既有LR/RF对照 | train训练 val早停与比较 | Macro-F1 逐类P/R 预测份额 | 分析损失权重取舍 |
| 分组五折CV | N/S/V/F | LR RF CNN | 仅train+val的37患者组 | 折均值 样本标准差 OOF汇总 | 探索患者组成敏感性 |
| 部署一致性 | 两任务 | 三模型 | 验证侧共200心拍×3 | 类别相同次数 最大概率差 | 工程复现验证 |

表{exp}最后一项的比较对象是同一模型的历史输出与部署输出，不以专家标签作为一致性判据，因此它不是新增的分类性能实验。固定测试虽在原训练后执行，本轮读取的是已有预测；回顾性查看不能恢复测试集未被触碰的状态。
'''
s=s.replace('# 第五章',exp+'\n# 第五章')
nv=(P/'draft/v2_nv_discussion.md').read_text(encoding='utf-8').replace('### 验证','### 5.1.1 验证')
j=json.loads((P/'evidence/v2_nv_partition_comparison.json').read_text(encoding='utf-8'))
nv+='\n\n表{nv} N/V CNN验证与测试逐类指标对比\n\n| 分区 | 类别 | 支持拍数 | Precision | Recall | F1 |\n|---|---|---|---|---|---|\n'
for sp,name in [('val','验证'),('test','测试')]:
    for cls,v in j['partitions'][sp]['per_class'].items():nv+='| '+name+' | '+cls+' | '+str(v['support'])+' | '+' | '.join(f'{v[k]:.4f}' for k in ['precision','recall','f1'])+' |\n'
nv+='\n图{nv}将患者真实V支持与N→V误分率并列展示。患者109的误分率为2477/2478，而患者111只有1拍真实V，其V召回即使达到1/1也不能视为稳定估计。完整12名患者的P/R/F1、支持数及错误方向保留于本轮核验表；图中不把没有V的患者填成V召回为0。\n\n![图{nv} N/V验证与测试分区的患者组成和误分表现](../figures/v2/fig16_nv_partitions.png)\n'
s=s.replace('## 5.2',nv+'\n\n## 5.2')
errors='''## 5.6 错误样本分析

图{old11}从已保存的四分类测试预测中精选N→S、F→N、F→V及V→N各一个案例，按各错误方向内预测类别置信度的中位附近选择，不代表随机样本。曲线读取对应NPZ的滤波后mV信号，横轴以专家标注为零点，标题给出记录及原始采样位置，完整样本编号由元数据追溯。

![图{old11} 四分类CNN的四个真实错误心拍](../figures/v2/fig11_errors.png)

记录212在采样点329145（914.292 s）的心拍原始符号为R，经映射属N，却被预测为S。这提示N组内部包含束支阻滞等不同符号，不能将N→S一律解释为健康心拍误报。记录208在313756（871.544 s）处为F→N，在271553（754.314 s）处为F→V；两例展示同一患者F心拍的不同误分方向。记录116在488586（1357.183 s）处为V→N，提示高V总体召回仍可包含局部漏分。

这些观察支持对错误类别和数据来源的复核，但没有完成临床专家盲评、特征遮挡或因果归因，不能仅由局部形态断言网络使用了特定P波或QRS规则。四分类F→N和F→V分别为216、154拍，且F测试几乎由患者208提供；病例与分布应结合解读。二分类模型的47拍N→V和11拍V→N属于另一标签任务，不能被四分类图例替代。本轮没有用案例调整阈值、损失权重或检查点。

## 5.7 实验结果综合讨论

当前固定划分下，CNN在N/V任务中获得较好的按拍汇总结果，但扩展为四分类后，优势没有继续保持。变化同时涉及标签边界、各类支持、患者来源及训练权重，现有对照不能把结果归因于单一因素。总体Accuracy容易受N类支撑，Macro-F1则暴露了稀有类F1接近零的情况，两者分别回答不同问题。

患者集中现象使大量相关心拍不能等同于大量独立患者证据。验证N→V主要集中在患者109、测试F几乎来自患者208，均说明按拍指标可能被少数来源主导；这并未证明模型记忆患者身份。权重改变了各类损失贡献与预测分布，但没有增加新的患者或节律上下文。探索性CV进一步揭示折间波动，仍不能替代外部数据。因而本研究支持既定数据库和协议下的模型比较及工程复现，并为进一步独立验证提出具体问题。

'''
s=re.sub(r'## 5\.6 .*?(?=# 第六章)',errors,s,flags=re.S)
# Clarify metric aggregation and improve the conclusion without changing values.
s=s.replace('五折均值与合并全部折外预测后计算的Macro-F1并不相同，','按拍汇总与逐患者平均也不等价：前者使心拍多的患者权重更大，后者需事先规定缺类患者如何处理。本文正式表格报告的是各折按拍Macro-F1，再对五折求均值，不是对37名患者F1的简单平均。五折均值与合并全部折外预测后计算的Macro-F1并不相同，')
s=s.replace('将定位误差传播纳入分类评估；','将定位误差传播纳入分类评估；')
s=s.replace('交互系统可继续完善教学任务和解释展示，','还应在独立数据上评价概率校准，并通过预先设计的用户研究检验互动教学效果。交互系统可继续完善教学任务和解释展示，')
# The system additions are integrated selectively, omitting writing-workflow prose.
sys=(P/'draft/v2_system_additions.md').read_text(encoding='utf-8')
def between(a,b):return sys.split(a,1)[1].split(b,1)[0].strip()
arch=between('## 系统架构与数据方向','架构图应表达')
infer=between('## 真实心拍推理流程','## 功能实现与验证证据').replace('`','')
fun=between('| 功能模块','静态类型检查');fun='| 功能模块'+fun
# Keep paper tables compact; complete file-level sources are in the audit report.
fun=fun.replace('`','')
fun=re.sub(r'\| ECG记录读取.*?\n', '| ECG记录读取 | WFDB真实信号与单位 | 后端窗口与浏览器画图 | 历史后端套件18项通过 | 后端日志与图{old13} |\n',fun)
fun=re.sub(r'\| 首次欢迎与教程.*?\n','| 首次欢迎与教程 | 可跳过引导与同拍跳转 | 浏览器及存储降级场景 | 历史文档22场景；当前项数未重核 | 欢迎文档与passed标记 |\n',fun)
for line in fun.splitlines():
    if line.startswith('|') and not line.startswith('|---'):
        pass
# Replace verbose developer paths in the final column with evidence labels.
fl=[]
for idx,line in enumerate(fun.splitlines()):
    if line.startswith('|') and idx>1:
        cells=[x.strip() for x in line.strip('|').split('|')]
        cells[-1]=['后端与全站日志','选拍E2E及图{old13}','欢迎回归记录','部署CSV及图{old14}','回放E2E与性能记录','科研API及图{old15}','图库E2E','游戏测试报告','欢迎教程记录'][len(fl)-2] if len(fl)>=2 and len(fl)-2<9 else cells[-1]
        line='| '+' | '.join(cells)+' |'
    fl.append(line)
fun='\n'.join(fl)
dep=between('| 任务 | 模型 | 验证心拍','## 互动教学模块');dep='| 任务 | 模型 | 验证心拍'+dep
teach=between('## 互动教学模块的依据与范围','## 正文截图替换建议')
chapter6='''# 第六章 ECG-AI系统设计与实现

## 6.1 系统总体架构

'''+arch+'''

图{old12}区分请求调用、标准化输入和文件读取。InferenceService承担推理编排，ECGStore提供信号与窗口，模型注册模块只读装载工件；科研图表沿独立的历史结果路径提供。

![图{old12} ECG-AI服务与数据调用架构](../figures/v2/fig12_architecture.png)

## 6.2 真实心拍推理流程与界面

'''+infer+'''

图{old13}放大工作台中的实际波形和标注，图{old14}集中展示同一心拍的三个真实模型输出。用户可以比较预测是否一致，专家标签仍是回顾性对照依据；单拍模型分数不代表总体性能。

![图{old13} ECG工作台的波形与心拍定位](../figures/v2/system_workbench_crop.png)

![图{old14} 同一心拍的三模型推理结果](../figures/v2/system_comparison_cards.png)

图注：图{old13}—图{old15}均来自2026年11月4日保留的真实浏览器截图。本轮裁剪核心区域以放大文字，其中图{old14}将三张结果卡片纵向重排；未重绘波形或改变预测值。它们是对应阶段已实现功能的证据，不称为本轮新运行截图。

## 6.3 功能实现与验证

表{func}将模块、验证方式和已有结果对应。软件测试日期为2026年11月3—4日，本轮复核源码及保存记录而未重新运行。18项后端和16项全站浏览器回归是各自阶段套件总数，不是每个模块的独立项数，也不相加为新的当前通过数。

表{func} 系统功能与历史验证证据

'''+fun+'''

模型实验中心读取已保存的指标与类别支持，局部界面如图{old15}。已有静态类型检查、生产构建和离线网络场景记录支持软件运行验证，但不能推出医学模型对新患者有效。

![图{old15} 模型实验中心的类别指标展示](../figures/v2/system_experiments_class_crop.png)

## 6.4 模型部署一致性

本轮直接汇总第三阶段的保存对照CSV，结果见表{deploy}。六组每组100次对照，预测类别均一致，输入最大绝对差均为0。

表{deploy} 部署与保存预测的一致性分组结果

'''+dep+'''

## 6.5 互动教学模块

'''+teach+'\n\n'
s=re.sub(r'# 第六章.*?(?=# 第七章)',lambda m:chapter6,s,flags=re.S)
# Upgrade figure assets while retaining the three already-readable signal figures.
for name in ['fig02_filter.png','fig03_window.png','fig07_nv_confusion.png']:
    shutil.copy2(P/'figures'/name,P/'figures/v2'/name)
s=s.replace('../figures/','../figures/v2/').replace('/v2/v2/','/v2/')
s=s.replace('![图{old8} 四分类各类别的受试者集中度]','![图{old8} 少数类在关键分区的患者集中度]')
s=s.replace('![图{old9} CNN权重策略的训练与验证表现]','![图{old9} CNN权重策略的验证侧Precision与Recall]')
# Visible figure numbers are assigned by narrative order, not filenames.
figmap={m[1]:i for i,m in enumerate(re.finditer(r'!\[图\{([^}]+)\}',s),1)}
tabmap={m[1]:i for i,m in enumerate(re.finditer(r'^表\{([^}]+)\}\s',s,re.M),1)}
s=re.sub(r'图\{([^}]+)\}',lambda m:'图'+str(figmap[m[1]]),s)
s=re.sub(r'表\{([^}]+)\}',lambda m:'表'+str(tabmap[m[1]]),s)
assert '{old' not in s
s=re.sub(r'<!--.*?-->','',s,flags=re.S) if False else s
# Keep native Word formula text as its editable authoring source.
s=s.replace('其中s_f是滤波信号，rᵢ','其中s下标f表示滤波信号，rᵢ').replace('μ_train和σ_train','训练均值μ与标准差σ').replace('p_(i,yᵢ)','p的下标(i,yᵢ)').replace('w_(yᵢ)','w的下标yᵢ')
s=s.replace('图1给出','图1给出')
target=P/'draft/ECG_AI_课程论文_修订版V2.md';target.write_text(s,encoding='utf-8')
index=['# V2正文图像索引','','| 图号 | 图题 | 文件 | 来源与处理 |','|---|---|---|---|']
for m in re.finditer(r'!\[(图(\d+) .+?)\]\((.+)\)',s):
    file=Path(m[3]).name
    origin=('保留的真实浏览器截图局部，来源与坐标见review/system_verification_v2.md' if file.startswith('system_') else '由真实CSV/JSON/NPZ或源码定义绘制，见tools/draw_v2_figures.py' if file not in ['fig02_filter.png','fig03_window.png','fig07_nv_confusion.png'] else '沿用V1真实实验信号图/混淆矩阵，原始来源见figures/figure_index.md')
    index.append(f'| {m[2]} | {m[1]} | {file} | {origin} |')
(P/'figures/v2/figure_index.md').write_text('\n'.join(index)+'\n',encoding='utf-8')
(P/'qa/v2/numbering.json').write_text(json.dumps({'figures':figmap,'tables':tabmap},ensure_ascii=False,indent=2),encoding='utf-8')
print(f'V2 retained and revised from V1: {len(figmap)} figures, {len(tabmap)} tables, {len(s)} source characters.')
