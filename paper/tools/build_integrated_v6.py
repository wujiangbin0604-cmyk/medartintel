"""Integrate completed rhythm/uncertainty research into a new V6, retaining V5."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'paper/reference/v5'
NAME = 'ECG_AI_课程论文_完整研究版V6'
OUT = ROOT / 'paper'
QA = OUT / 'qa/v6'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(caption, headers, rows):
    return '\n'.join([caption, '', '| ' + ' | '.join(headers) + ' |',
                      '|' + '|'.join('---' for _ in headers) + '|',
                      *['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]])


def report_table(report, start):
    lines = report.splitlines()
    pos = next(i for i, line in enumerate(lines) if line.startswith(start))
    end = pos
    while end < len(lines) and lines[end].startswith('|'):
        end += 1
    return [[v.strip() for v in line.strip('|').split('|')]
            for line in lines[pos + 2:end]]


def renumber_references(text):
    body, tail = text.split('# 参考文献', 1)
    refs_text, endmatter = tail.split('# 附录', 1)
    refs = {int(n): value for n, value in re.findall(r'^\[(\d+)\] (.+)$', refs_text, re.M)}
    order = []
    pattern = re.compile(r'\[(\d+(?:[-,]\d+)*)\]')
    def nums(value):
        result = []
        for token in value.split(','):
            if '-' in token:
                a, b = map(int, token.split('-')); result.extend(range(a, b + 1))
            else:
                result.append(int(token))
        return result
    for hit in pattern.finditer(body):
        for n in nums(hit[1]):
            assert n in refs, n
            if n not in order: order.append(n)
    assert set(order) == set(refs), (order, refs)
    mapping = {old: new for new, old in enumerate(order, 1)}
    body = pattern.sub(lambda m: '[' + ','.join(str(mapping[n]) for n in nums(m[1])) + ']', body)
    return (body.rstrip() + '\n\n# 参考文献\n\n' + '\n\n'.join(
        f'[{mapping[n]}] {refs[n]}' for n in order) + '\n\n# 附录' + endmatter), mapping


def main():
    QA.mkdir(parents=True, exist_ok=True)
    source = BASE / 'draft/ECG_AI_课程论文_自然表达版V5.md'
    reference = BASE / 'final/ECG_AI_课程论文_自然表达版V5.docx'
    assert sha(reference) == '1c54aa084246ffc7771cf736c4c9b66ff2df098bf6c72d835e6a432e89e94e93'
    text = source.read_text(encoding='utf-8')
    report = (ROOT / 'research_extensions/INNOVATION_REPORT.md').read_text(encoding='utf-8')
    subtitle = '形态与历史节律融合及患者独立可靠性分析'
    text = text.replace('副标题：基于一维卷积网络的患者独立评估', '副标题：' + subtitle)

    abstract = '''## 摘要

本文以MIT-BIH专家标注心拍为对象，研究形态与历史节律融合在患者独立分类中的表现，并将真实模型、错误分析和拒识结果整合到ECG-AI教学系统。原实验排除四条起搏记录，将44条记录归为43个患者组，保持31/6/6训练、验证和测试划分。单导联信号经过0.5—40 Hz双向滤波，围绕标注位置截取253点窗口。原N/V卷积模型的测试Macro-F1为0.9865，验证值为0.6630；原四分类卷积模型的测试Macro-F1为0.4460，说明二分类结果不能代表S/F识别能力。既有三种子损失与四维RR对照作为历史探索结果保留。

新增研究仅使用原训练和验证的37个患者组、86,286拍，不使用原测试患者拟合或选阈值。七项当前及过去RR特征与七项有效性掩码构成节律输入，采用五折患者互斥外层评价，并在每折另留内部早停和阈值校准患者。四模型、三种子共完成60次训练。每种子合并折外预测后，形态CNN、仅节律MLP、融合模型和节律错配对照的Macro-F1均值±种子样本标准差分别为0.3584±0.0259、0.3754±0.0030、0.4628±0.0230和0.3530±0.0147。融合相对形态基线提高0.1044±0.0116，但S类平均召回率由0.4514降至0.4060，F类F1仍仅为0.0357。患者改善与下降并存，少数类支持也较集中。

以独立内部校准患者的90%分位数冻结拒识阈值后，融合模型最大分数代理的外层覆盖率为0.8795，接受拍错误率由全部拍的0.1968降至0.1611，但F类以全部支持为分母的保留召回率降至0.0047。拒识减少部分接受错误，也可能丢弃重要少数类，不能解释为临床安全保证。系统支持真实心拍追溯、患者留出模型推理和互动教学。贡献在于同预算消融、患者与类别层面的证据检查及可复现工程整合；结论限于已被回顾性分析的开发患者，系统依赖专家定位和离线滤波，尚无外部或前瞻性临床验证。

关键词：心电图，心拍分类，历史RR间期，患者独立评估，选择性分类

'''
    text = re.sub(r'## 摘要\n.*?(?=## Abstract\n)', lambda m: abstract, text, flags=re.S)
    english = '''## Abstract

This study investigates whether historical rhythm features complement heartbeat morphology under patient-independent evaluation, and integrates the resulting models and reliability analyses into the ECG-AI teaching application. The MIT-BIH Arrhythmia Database supplied expert-centered, single-lead heartbeat windows. Excluding four paced recordings left 44 recordings and 43 patient groups; the original 31/6/6 training, validation and test allocation was retained. Signals underwent offline 0.5–40 Hz forward-backward filtering before extraction of 253-sample windows. The original N/V convolutional model achieved test and validation macro-F1 values of 0.9865 and 0.6630, respectively, while its four-class test macro-F1 was 0.4460. Earlier three-seed loss and four-feature RR experiments are retained as historical exploratory evidence.

The new investigation used only the original training and validation pool: 86,286 beats from 37 patient groups. Seven current and historical RR features and seven validity masks formed the rhythm input. Five outer patient-disjoint folds were combined with separate inner fitting, early-stopping and threshold-calibration groups. Four models and three training seeds yielded 60 completed runs. Across seeds, pooled out-of-fold macro-F1 was 0.3584±0.0259 for the morphology CNN, 0.3754±0.0030 for the rhythm-only MLP, 0.4628±0.0230 for fusion, and 0.3530±0.0147 for an equally sized rhythm-mismatch control. Values after ± are sample standard deviations across training seeds, not patient confidence intervals. Fusion improved macro-F1 by 0.1044±0.0116 over the matched morphology baseline. However, mean S recall decreased from 0.4514 to 0.4060, and mean F-class F1 remained only 0.0357. Gains varied across patients and minority-class evidence was concentrated.

Rejection thresholds were frozen at the 90th percentile of uncertainty scores from separate inner calibration patients. For fusion with the maximum-score proxy, outer coverage averaged 0.8795 and accepted-beat error was 0.1611, compared with an all-beat error of 0.1968. Yet retained F recall, measured against all true F beats, fell to 0.0047. Lower accepted error therefore coexisted with loss of minority-class coverage. Softmax scores and entropy were uncalibrated proxies, not clinical risk estimates. The application provides traceable real-beat inspection, patient-held-out research inference and interactive teaching. The contribution is a controlled, reproducible investigation and its teaching integration. Findings concern retrospectively analyzed development patients, depend on expert localization and offline processing, and do not establish external or prospective clinical effectiveness.

Key words: electrocardiogram, heartbeat classification, historical RR intervals, patient-independent evaluation, selective classification

'''
    text = re.sub(r'## Abstract\n.*?(?=<!--TOC-->)', lambda m: english, text, flags=re.S)
    text = text.replace('不包含任意原始ECG的自动事件发现，也不以提出新网络算法为目标。',
                        '不包含任意原始ECG的自动事件发现。新增研究检验历史节律的补充信息，并考察拒识是否在减少接受错误的同时损失少数类覆盖；工作以受控实证和系统整合为目标。')
    old_work = text[text.index('本项目完成患者分组数据集'):text.index('![图1-1')]
    text = text.replace(old_work, '''本项目保留原患者划分、六个生产模型与历史结果，完成三类模型比较、少数类及患者差异分析、损失函数和四维RR探索。随后在原开发患者内开展七项历史节律及缺失掩码的四模型消融，分开拟合、早停、阈值校准和外层评价患者，报告全部五折、三个种子的60次训练。研究进一步用覆盖率、接受错误和逐类保留召回分析拒识取舍，并将结果和患者留出模型接入原有系统。形态与节律融合已有研究基础[4,8]，本项目此前也已有RR分支，因此贡献在对照设计、完整结果和可追溯教学实现，不主张首次提出CNN与RR拼接。图1-1给出原数据与模型流程，新增分支见第3章。

## 1.5 研究问题与可检验假设

新增研究提出三个问题。H1：在相同训练预算、分组与评价规则下，融合模型是否提高部分异常心拍的识别指标；H2：这种变化是否具有类别差异，尤其需要同时观察S类精确率与召回率、F类支持与误报；H3：按拍汇总的提升是否主要来自少数患者。三个假设允许被结果拒绝，不预设融合必然改善。可靠性分析另问：以训练侧患者设定的拒识规则，能否在外层患者中识别较多错误，以及为此失去哪些类别的覆盖。

选择性分类通过拒绝部分样本权衡覆盖率与接受样本的错误风险[14]。已有深度网络研究采用最大响应等分数构造拒识，但其统计保证依赖特定算法和条件[15]。神经网络分数也可能未校准[16]。本文仅实现独立校准患者上的分位数阈值，不将分数视为正确概率，也不沿用其他研究的风险保证。

''')
    text = text.replace('# 第3章 模型设计', '''## 2.6 新增研究的开发池与事件对齐

新研究将原训练与验证患者合为开发池，共37个患者组、86,286拍；原六个测试患者完全排除。N/S/V/F分别为77,290、2,751、5,816和429拍，对应37、28、27和14个有该类心拍的患者组。该合并不改变原31/6/6分区，所有来源仍保留原分区键。数据程序按sample_id逐条核对原始注释索引、采样位置、符号和受试者键，没有打开原测试NPZ。专家心拍事件先按固定WFDB beat符号集合筛选，包含Q等非目标心拍，再对目标拍构建RR；节律改变、伪迹等非心拍标注不计入事件。这样避免把目标类别选择误当成相邻心拍关系。类别符号仅用于判断是否为beat事件，其数值不送入节律网络。

开发患者已在项目历史分析中出现，因此新的折外预测仍属于回顾性开发证据。外层互斥可以防止本轮同一患者同时拟合与评价，不能撤销已有的研究者数据接触，也不能把这37组变成新的外部队列。

# 第3章 模型设计''')
    features = [
        ['当前RR', '(rᵢ−rᵢ₋₁)/360', '至少两个专家心拍位置'],
        ['前一RR', '(rᵢ₋₁−rᵢ₋₂)/360', '至少三个位置'],
        ['相邻比值', '当前RR/前一RR', '两个RR均可用'],
        ['历史归一比', '当前RR/历史中位数', '至少一个历史RR'],
        ['历史中位数', '此前最多五个RR的中位数', '历史不含当前RR'],
        ['历史MAD', '历史RR绝对偏差的中位数', '至少两个历史RR，不作尺度放大'],
        ['相对历史变化', '(当前RR−历史中位数)/历史中位数', '至少一个历史RR'],
    ]
    models = report_table(report, '|模型|输入与结构|参数量|')
    methods = '''## 3.6 历史节律与形态的双分支模型

为区分输入信息的收益与训练方案差异，新研究重新训练同预算形态基线，而不将新模型与旧生产检查点直接排名。节律在每条记录内从头计算，当前拍仅能读取到当前及此前的专家位置，不使用下一RR、标签值、患者编号或记录编号。表3-3列出七项特征。历史集合为当前RR之前最多五个已完成RR，其单位为秒；缺失项初始为NaN，配套有效性掩码取0，有效项取1。

''' + table('表3-3 七项历史节律特征', ['特征', '计算定义', '可用条件'], features) + '''

七项特征的填充中位数、填充后的均值和总体标准差仅由当前外层折的内部拟合患者估计，标准差下限为10⁻⁸。全缺失列按协议填0，不按标签选择默认值；缺失历史的事实由掩码保留。缩放后的七维数值与七维掩码拼成14维输入，不实施事后裁剪。波形直接复用原滤波窗，并仅在内部拟合患者上重新估计标量均值与标准差。早停、校准和外层患者均调用冻结变换，不能复用原31组训练统计代替本轮拟合统计。

''' + table('表3-4 新增四模型结构与参数量', ['模型', '输入与结构', '参数量'], models) + '''

A2沿用原CNN的64维形态表示，节律分支按14→32→16变换并使用ReLU，两路拼接为80维后线性输出四类logits，图3-2给出真实结构。A0、A1、A2依次检验形态、节律及组合信息；A3与A2参数量相同，在每个拟合、早停、校准和外层评价子集内对节律数值及掩码整体作固定无自配对置换，不使用标签构造置换，也不跨子集交换。置换可在同一子集的不同患者间错配，并在全部种子中复用。因此，A3主要检查正确对应关系是否重要；它也改变输入相关结构和优化过程，不能单独分解全部生理机制。A2与A0参数量不同，仍需保留容量混杂这一限制。

![图3-2 七项节律与有效性掩码的双分支融合结构](../../research_extensions/rhythm_fusion/figures/cv_cpu_v1/01_architecture.png)

图示对应实际模型定义，结构示意不表示某个神经元的激活。历史RR不含未来间期，但原波形含标注后0.4 s内容并经过双向滤波，因此完整流程仍为专家定位条件下的离线分类。

## 3.7 预测不确定性与固定拒识规则

四类softmax向量记为p，最大分数代理定义为uₘₐₓ=1−maxₖpₖ，信息熵代理定义为uH=−Σₖpₖln pₖ，熵单位为nat，不除以ln 4。每个模型、折与种子从其独立内部校准患者取得分数，以numpy的higher规则取90%分位数τ，并在u≤τ时接受。阈值计算只读取分数，不读取校准标签；标签仅用于事后评价。90%为预先设定的教学保留预算，不是临床安全界限，外层覆盖率可以偏离90%。本实现没有进行温度缩放或其他概率校准。

拒识保持原预测类别，另标记是否接受，不把被拒样本改写为正确预测。程序保存全部120个模型—折—种子—代理阈值与来源，并报告四模型、三种子、两代理的24组汇总，不根据外层结果选取最好模型或阈值。

'''
    text = text.replace('# 第4章 实验设计与评价指标', methods + '# 第4章 实验设计与评价指标')
    inner = report_table(report, '|fold|拟合|早停|阈值校准|外层评价|')
    design = '''## 4.4 新增五折三种子研究协议

外层采用固定随机状态20261118的StratifiedGroupKFold五折，患者组互斥且各患者只进入一个外层评价折；分层仅尽量保持类别比例，不保证各折类别相同。每个外层训练侧再用六折分组划分：内部第0折早停，第1折阈值校准，其余患者实际拟合。四类患者两两互斥，拟合统计、类别权重、梯度更新、epoch选择、阈值冻结和外层评价的角色分开。表4-2列出患者数与心拍数。

''' + table('表4-2 新研究各外层折的内部与评价规模', ['外层折', '拟合患者/拍', '早停患者/拍', '校准患者/拍', '评价患者/拍'], inner) + '''

三个训练随机种子为20261118、20261119和20261120；这些整数是随机状态标识，不代表实验日期。每个种子复用相同五折和A3映射。实际完成五折×三种子×四模型共60次训练；另四次小规模冒烟运行不计入结果。全部模型使用内部拟合侧逆频率加权交叉熵、Adam、学习率0.001、weight decay 10⁻⁵、批大小512，最多12轮，早停耐心值4。检查点按内部早停患者的固定四类Macro-F1选择，不读取外层表现。CPU训练固定两线程；本轮没有CUDA训练。相较历史25轮实验，本轮拟合患者更少且预算更短，故仅在本轮A0—A3之间作受控比较。

先完成单种子预算，再在不更改超参数的条件下补充另两个预定种子，组件清单保留各轮源码及工件哈希。既有完成任务按哈希检查后跳过，未完成任务从该次训练重新开始，不声称逐批恢复优化器。原正式测试患者不参与本轮拟合、早停、校准或效果确认。

## 4.5 汇总单位与选择性评价

主指标先对每种子合并五折全部折外预测，再计算固定N/S/V/F四类Macro-F1，最后报告三个种子的均值和样本标准差（ddof=1）。折均值与合并值因非线性和类别支持不同而不等同。患者Macro-F1也固定四类，缺失类别按0处理；它用于同一患者的成对比较，不能与只平均该患者实际出现类别的指标混用。三个种子反映训练随机性，37个患者和86,286拍不乘以3。

覆盖率以接受拍数除以全部拍数；接受错误率的分母为接受拍数，拒识错误率的分母为拒识拍数。各类接受率以全部真实该类拍数为分母。为防止删去难例后产生误解，逐类同时报告接受子集召回率与全体分母召回率：两者的分子均为接受且正确的该类拍数，前者除以接受的真实该类数，后者除以全部真实该类数。接受精确率则以接受且预测为该类的拍数为分母。无分母时保留计数并注明未定义；分类库逐类零除按0汇总，不将其解释为确定的零风险。

错误识别AUROC以预测是否错误为二元目标，只评价不确定性代理对当前折外错误的排序。Risk–Coverage曲线由冻结外层预测作描述性扫描，同分数一并接受，不用于反选部署阈值。另按患者整组进行每种子1000次成对bootstrap，并保留每组全部相关心拍；这些区间仅为既有开发患者的条件性敏感性描述，训练折重叠也带来依赖，本文不据此作独立心拍显著性检验或外部有效性保证。

'''
    text = text.replace('# 第5章 实验结果与分析', design + '# 第5章 实验结果与分析')
    text = text.replace('## 5.7 实验结果综合讨论', '## 5.7 原固定分区结果讨论')
    text = text.replace('## 5.8 多种子受控改进实验', '## 5.8 既有三种子损失与四维RR探索')

    overall = report_table(report, '|模型|OOF Macro-F1均值±SD|Accuracy|Balanced Accuracy|参数|单拍ms中位数|')
    seeds = report_table(report, '|种子|A0|A1|A2|A3|A2−A0|')
    allclass = report_table(report, '|模型|类|Precision均值±SD|Recall均值±SD|F1均值±SD|支持拍数|独立患者|')
    selected = [[r[0] + '/' + r[1], *[r[i].split(' ± ')[0] for i in (2, 3, 4)], r[5] + '/' + r[6]]
                for r in allclass if r[0] in ('A0', 'A2')]
    uncertainty = report_table(report, '|模型|代理|Coverage均值±SD|全部错误率|接受拍错误率|拒识拍错误率|错误识别AUROC|')
    uncertainty = [[r[0] + '/' + ('最大分数' if r[1] == 'max_score' else '熵'),
                    *[v.split(' ± ')[0] for v in r[2:]]] for r in uncertainty]
    accepted = report_table(report, '|代理|真实类|接受率|保留Precision|保留Recall|全体分母Recall|原支持/患者|')
    accepted = [[('最大分数' if r[0] == 'max_score' else '熵') + '/' + r[1], *r[2:]] for r in accepted]
    results = '''## 5.10 形态与历史节律的四模型消融结果

本节结果来自第4.4节的新开发池协议，与表5-7的旧验证/测试结果分开解释。表5-9显示，A2合并OOF Macro-F1均值为0.4628，比A0高0.1044±0.0116；三个种子的差值均为正。A1为0.3754，表明历史节律在当前数据中含有判别信息，但仍不足以独立解决四分类。A3与A2容量相同而表现回落，两者差值为0.1097±0.0114，支持正确对应的节律信息具有作用；由于随机错配也改变了优化与输入结构，该证据不能排除全部其他解释。

''' + table('表5-9 新增四模型的合并OOF结果', ['模型', 'Macro-F1均值±SD', 'Accuracy均值±SD', '平衡准确率均值±SD', '参数量'], [r[:5] for r in overall]) + '\n\n' + table('表5-10 每个预定种子的合并OOF Macro-F1', ['种子', 'A0', 'A1', 'A2', 'A3', 'A2−A0'], seeds) + '''

![图5-12 四模型全部预定种子的OOF Macro-F1](../../research_extensions/rhythm_fusion/figures/cv_cpu_v1/12_seed_comparison.png)

图5-12采用全部三个种子，不以最好一次运行替代汇总。A2在15个种子—折组合中的Macro-F1范围为0.4236—0.5858，A0为0.2725—0.4472。种子总体差值同向不代表每类、每折和每位患者都得到稳定改善。

''' + table('表5-11 形态基线与融合模型的逐类OOF均值', ['模型/类', 'Precision', 'Recall', 'F1', '支持拍/患者'], selected) + '''

表5-11中的P、R、F1是每种子合并OOF指标的三种子均值，不是先平均P/R再计算F1；样本支持只计一次。全部四模型的逐类种子波动见图5-13及复现报告。S的平均Precision从0.0550升至0.1030，Recall反而从0.4514降至0.4060，F1从0.0980升至0.1642。S召回的成对变化为−0.0453±0.2117，不能只报告首个种子中召回上升。V的F1从0.5652升至0.7629，是当前改善的重要组成。F的F1虽由0.0104升至0.0357，差值仅为0.0253±0.0547，平均Precision仍为0.0195，部分种子以大量误报换取召回，不支持F识别已经解决。

![图5-13 四模型逐类F1的全部种子结果](../../research_extensions/rhythm_fusion/figures/cv_cpu_v1/13_class_seed_variability.png)

## 5.11 患者异质性与结果敏感性

开发池S类有28位患者贡献2,751拍，其中患者232贡献1,376拍，占50.02%；F类有14位患者贡献429拍，其中患者213贡献362拍，占84.38%。患者来源集中使按拍统计容易受个体形态与节律影响，数百拍F不能视为数百个独立患者。

比较A2与A0的固定四类患者Macro-F1，三个种子分别有31/30/31名患者改善，5/5/4名下降，1/2/2名不变。三次训练净纠正错误最多者均为患者112，但暂时去除其折外预测后，其余患者的合并Macro-F1差值仍为+0.0866、+0.0964和+0.1076。该事后计算没有重新训练，只说明总体差值不完全由这一位患者解释，不能据此排除若干患者共同主导或证明外部泛化。

![图5-14 各预定种子与外层折的性能波动](../../research_extensions/rhythm_fusion/figures/cv_cpu_v1/07_fold_seed_variability.png)

H1在当前开发协议下获得有限支持：总体和部分异常类指标改善。H2得到类别差异证据，S体现精确率与召回的取舍，F仍不可靠。H3作为“可能主要由少数患者主导”的担忧需要患者分析，结果不支持把全部增益归于净纠正最多的一位患者，但也没有排除其他患者组成效应。所有判断限于本轮37个开发患者及12轮训练预算。

## 5.12 不确定性拒识的收益与类别损失

全部四模型和两种代理结果见表5-12，表中为三个种子的指标均值，完整标准差与阈值保存在复现文件。A2最大分数代理的平均外层覆盖率为0.8795±0.0151，全部拍错误率为0.1968±0.0158，接受拍错误率为0.1611±0.0102，拒识拍错误率为0.4522±0.0803。熵代理的对应覆盖率与接受错误率为0.8743±0.0099和0.1635±0.0060。两种方法都在这批数据中将较多错误排至拒识侧，但未达到预定校准覆盖率的外部保证。

''' + table('表5-12 固定阈值下四模型的覆盖率与错误率均值', ['模型/代理', '覆盖率', '全部错误', '接受错误', '拒识错误', '错误AUROC'], uncertainty) + '''

A2最大分数代理在三个种子分别接受77,055、74,476和76,134拍，分母均为86,286；拒识9,231、11,810和10,152拍。熵代理分别接受76,322、75,382和74,617拍。每种子的覆盖与误差由各自完整折外预测计算，不把跨种子的重复心拍合成新的样本量。图5-15仅选预定首个种子20261118展示风险—覆盖曲线，全种子固定阈值结果仍完整报告，曲线没有用于挑选阈值。

![图5-15 首个预定种子的描述性风险与覆盖率曲线](../../research_extensions/rhythm_fusion/figures/cv_cpu_v1/09_risk_coverage.png)

''' + table('表5-13 融合模型拒识后的逐类均值与分母', ['代理/类', '类接受率', '接受P', '接受R', '全体分母R', '原支持/患者'], accepted) + '''

拒识的主要局限是F类损失。最大分数代理平均只接受59.52%的真实F拍，F的接受子集Recall为0.0109，而以全部429拍为分母的保留Recall仅为0.0047；熵代理分别为0.0092和0.0039。拒识前A2的F Recall均值为0.2230，因此接受错误率下降伴随明显的少数类检出损失。不能把被拒拍当作已识别异常，也不能只用接受子集的准确率宣称模型可靠。各患者拒识比例仍不同，完整患者计数随结果文件保留。

## 5.13 新旧研究的关系与有效性限制

新旧实验的患者范围、训练预算、损失、早停与汇总方式不同。旧focal_sqrt_rr的旧测试Macro-F1为0.5002±0.0036，新A2的开发OOF为0.4628±0.0230，不能按数值高低判定升级效果。本轮有效对照为同协议A0—A3，原六个生产模型不替换。

当前外层折隔离了本轮拟合患者，但全部开发患者已有历史接触，数据只有一个数据库，F支持高度集中，三个种子也只考察训练随机性。RR依赖专家事件定位，信号包含双向滤波和右侧窗口；本研究既未评价自动R峰检测误差，也未进行设备外、中心外或前瞻性验证。分位数阈值没有概率校准和临床风险上界。上述限制决定了成果可用于实验分析与教学演示，尚不能用于诊疗决策。

'''
    text = text.replace('# 第6章 ECG-AI系统设计与实现', results + '# 第6章 ECG-AI系统设计与实现')
    system = '''## 6.6 节律融合与可靠性实验室

新增页面/rhythm-lab由既有React与Ant Design界面承载，后端/api/rhythm/summary读取真实汇总，/samples提供可追溯样本，/beat根据record_id和annotation_sample读取WFDB并加载研究检查点。模型注册保存模型、折、种子、评价患者与SHA-256；单拍演示固定采用首个预定种子，按该患者的外层留出折选择模型，不从外层成绩选择最好种子。原正式CNN另列并提示其可能接触该患者，单个案例不构成公平模型排名。对原正式测试患者，研究接口拒绝新增模型推理，以维持研究范围。

页面对应展示14维节律输入、缺失掩码、双分支结构、全部种子/折/类别结果、错误样本和可靠性分母。指标与图形来自真实保存文件，不填充预计收益；尚未执行的新N/V消融保持空状态，缺历史给出原因。图6-5为本地实际页面截图。Heartbeat Hunter仅在作答结束并揭示专家答案后提供同一记录/采样点的研究链接，原评分、计时、存档与关卡判定不改变。已揭示答案的关卡不能作为新模型的独立测试。

![图6-5 节律融合与可靠性实验室的实际运行页面](../../research_extensions/validation/screenshots/rhythm_top_1440.png)

## 6.7 发布包完整性与实际验证范围

完整运行包包含48条原始记录、六个原生产模型、60个独立研究检查点、预构建前端、科研结果、固定依赖和部署脚本。网页推理不需要训练NPZ，也不要求服务器安装Node.js或重新训练。SHA-256清单校验文件内容，启动检查加载原模型、全部研究结构及120个阈值，再核验六模型参考预测、研究单拍输出、62个游戏关卡和接口数据。新旧模型分目录保存，已有游戏数据使用固定Compose项目名及命名卷保留。

发布阶段已有107项Python检查通过，15项浏览器交互检查通过，包含新增页面、原游戏流程、390像素窄屏和减少动态效果。独立下载/导出目录启动验证不使用原工作区的训练NPZ、前端依赖或项目导入路径；Python依赖复用已验证的本机3.12环境。Ubuntu部署使用Docker、固定CPU依赖及独立数据库卷，已有Linux依赖可用性检查，但本机没有执行Linux容器构建，因此不将Windows解压启动验证写成服务器实机部署成功。软件检查证明数据和模型按设计加载，不能替代医学有效性或教学效果研究。

'''
    text = text.replace('# 结论', system + '# 结论')
    conclusion = '''# 结论

本项目在MIT-BIH专家标注心拍上完成数据处理、三类原模型对照、患者来源分析与ECG-AI教学系统整合。原31/6/6患者划分、六个生产模型和历史报告均保留。N/V测试Macro-F1为0.9865而验证值为0.6630，重推支持结果一致，误报主要集中于患者109；四分类和旧损失/RR探索进一步说明总体指标与少数类识别可以明显分离。旧测试复用的探索范围在文中单独说明。

新增研究在原训练与验证37个患者组中，以七项历史节律及七项掩码构建双分支模型，完成五折、三种子、四模型共60次训练，分开拟合、早停、阈值校准和外层患者。A2合并OOF Macro-F1为0.4628±0.0230，相对同预算A0提高0.1044±0.0116；同容量错配对照回落，支持对应节律信息在本轮条件下的价值。但S召回平均下降，F的F1仍低，患者改善与退化并存，不能称为少数类全面解决。既有研究和本项目早期实现均已融合RR，本文贡献在受控比较、完整患者追溯和教学整合。

独立内部校准患者的固定拒识规则降低了接受拍错误率，最大分数代理覆盖率为0.8795、接受错误率为0.1611；同时F类全体分母保留召回率降至0.0047，揭示总体风险下降与少数类损失可以共存。软分数和熵尚未校准，拒识没有得到临床风险保证。系统将真实波形、标签、患者留出模型、错误案例和互动教学相连，工程验收与医学泛化结论分别陈述。

本研究只有一个已被历史分析的数据库，独立患者数量有限，少数类支持集中，模型依赖专家定位和离线双向滤波。后续应在新增患者上预先冻结流程，评价自动定位误差、设备与中心变化、概率校准和类别覆盖，并在教学场景开展用户研究。现阶段成果适用于课程实验和结果复核，不能作为临床诊断系统或医学能力评估工具。

'''
    text = re.sub(r'# 结论\n.*?(?=# 参考文献)', lambda m: conclusion, text, flags=re.S)
    refs = '''[14] EL-YANIV R, WIENER Y. On the foundations of noise-free selective classification[J]. Journal of Machine Learning Research, 2010, 11(53): 1605-1641. https://jmlr.org/papers/v11/el-yaniv10a.html.

[15] GEIFMAN Y, EL-YANIV R. Selective classification for deep neural networks[C]//Advances in Neural Information Processing Systems. 2017, 30.

[16] GUO C, PLEISS G, SUN Y, et al. On calibration of modern neural networks[C]//Proceedings of the 34th International Conference on Machine Learning. PMLR, 2017, 70: 1321-1330. https://proceedings.mlr.press/v70/guo17a.html.

'''
    text = text.replace('# 附录1', refs + '# 附录1')
    text = text.replace('# 致谢', '''# 附录2 新增研究与部署复现索引

代码及数据来源见GitHub仓库https://github.com/wujiangbin0604-cmyk/medartintel。新增实现位于research_extensions/rhythm_fusion/src及uncertainty/src，配置、患者折、数据对齐和审计文件分别保存。原开发池构建后可运行python -m research_extensions.rhythm_fusion.src.run --help核对训练入口；完整指令以该目录README为准。cv_cpu_v1与cv_cpu_repeats_v1保留三种子的独立检查点和逐拍预测；model_registry.json记录哈希及留出患者。uncertainty/results/cv_cpu_v1/summary.json保存全部阈值、患者拒识和逐类分母，INNOVATION_REPORT.md提供完整表格，figures/cv_cpu_v1/catalog.json列出图源与哈希。

运行包使用deploy/ubuntu22/bundle_manifest.json校验完整性。Windows需64位Python 3.12，可运行start-local.ps1；Ubuntu 22.04 amd64优先运行deploy/ubuntu22/deploy.sh，首次构建需要联网下载基础镜像和固定CPU依赖。网页运行无需训练NPZ，论文复现实验则需要按项目预处理步骤重新生成开发数组。完整上传、启动、健康检查及保留游戏卷的命令随本次发布包说明交付。本文的60次训练和可靠性数值以本地完成工件为依据，不把服务器部署或未来复现写成已经发生。

# 致谢''')
    text = text.replace('新增受控训练实际使用Python', '既有25轮损失与四维RR受控训练使用Python')
    text = text.replace('新增训练按3.5节方案执行', '既有损失与四维RR对照按3.5节执行，本轮七项RR与掩码按3.6节执行')
    text = text.replace('四分类五折StratifiedGroupKFold仅使用', '既有四分类五折StratifiedGroupKFold仅使用')
    text = text.replace('## 6.3 功能实现与验证', '## 6.3 既有系统功能验证')
    text = text.replace('软件验证覆盖真实数据读取', '2026年11月17日的既有软件验证覆盖真实数据读取')
    text = text.replace('但公网仍运行既有版本，新增导出与健康修复尚未远程发布。',
                        '该轮记录的公网仍运行既有版本，彼时新增导出与健康修复尚未远程发布；后续发布验证见6.7节。')
    text = text.replace('表6-1 系统功能与最终实际验证', '表6-1 既有系统功能与实际验证')
    text, mapping = renumber_references(text)
    draft = OUT / 'draft' / (NAME + '.md')
    draft.write_text(text, encoding='utf-8')
    for caption, rel in re.findall(r'!\[(.+?)\]\((.+?)\)', text):
        assert (draft.parent / rel).resolve().is_file(), (caption, rel)
    assert text.count('$$') == 7
    spec = importlib.util.spec_from_file_location('v3_builder', ROOT / 'paper/tools/build_final_v3.py')
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    builder.V2_DOCX = reference
    builder.V3 = draft
    builder.DOCX = OUT / 'final' / (NAME + '.docx')
    builder.QA = QA
    builder.SUBTITLE = subtitle
    builder.EN_SUBTITLE = 'Morphology and Historical Rhythm Fusion with Patient-independent Reliability Analysis'
    builder.build_docx(text)

    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt
    doc = Document(builder.DOCX)
    # A separate page-break paragraph can itself spill onto an otherwise empty
    # page when a chapter ends near the bottom. Put the break on the heading.
    for p in doc.paragraphs:
        if p.style.name != 'V3Chapter':
            continue
        previous = p._p.getprevious()
        if previous is not None and previous.tag == qn('w:p'):
            breaks = previous.findall('.//' + qn('w:br'))
            if any(b.get(qn('w:type')) == 'page' for b in breaks) and not ''.join(previous.itertext()).strip():
                previous.getparent().remove(previous)
        p.paragraph_format.page_break_before = True
    for p in doc.paragraphs[:25]:
        if p.text == '2026年11月17日':
            p.runs[0].text = '2026年11月19日'
    # Preserve the V5 visual system; numeric summary columns need more room.
    for t in doc.tables:
        headers = [c.text for c in t.rows[0].cells]
        if headers == ['模型', 'Macro-F1均值±SD', 'Accuracy均值±SD', '平衡准确率均值±SD', '参数量']:
            widths = [.48, 1.55, 1.55, 1.75, .67]
        elif headers == ['模型/类', 'Precision', 'Recall', 'F1', '支持拍/患者']:
            widths = [.8, 1.05, 1.05, 1.05, 2.05]
        elif headers == ['外层折', '拟合患者/拍', '早停患者/拍', '校准患者/拍', '评价患者/拍']:
            widths = [.65, 1.4, 1.4, 1.4, 1.15]
        else:
            continue
        for col, width in zip(t.columns, widths): col.width = Inches(width)
        for row in t.rows:
            for cell, width in zip(row.cells, widths):
                cell.width = Inches(width)
    doc.save(builder.DOCX)
    builder.check_docx(builder.DOCX)
    manifest = {
        'version': 'V6 complete research integration', 'date_Asia_Shanghai': '2026-11-19',
        'source_markdown': str(source), 'source_md_sha256': sha(source),
        'reference_docx': str(reference), 'reference_sha256': sha(reference),
        'retains_original_V5': True, 'original_experimental_results_rewritten': False,
        'new_runs': 60, 'new_seeds': [20261118, 20261119, 20261120],
        'independent_development_patient_groups': 37, 'independent_development_beats': 86286,
        'new_original_test_evaluation': False, 'reference_renumbering': mapping,
        'new_sources_verified': ['https://jmlr.org/papers/v11/el-yaniv10a.html',
                                 'https://papers.neurips.cc/paper_files/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html',
                                 'https://proceedings.mlr.press/v70/guo17a.html'],
        'new_results_report_sha256': sha(ROOT / 'research_extensions/INNOVATION_REPORT.md'),
        'draft_sha256': sha(draft), 'figure_count': len(re.findall(r'^!\[', text, re.M)),
        'body_cjk_characters': len(re.findall(r'[\u4e00-\u9fff]', text)),
        'render_status': 'PENDING'
    }
    (QA / 'integration_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    (QA / 'artifact.md').write_text(f'''# V6 reference and execution contract

Reference: {reference}; SHA-256 {sha(reference)}. V5 is immutable.
Use the existing A4 cover, university artwork, author fields, original title, three-section page system, and seven native editable equations.
V5 uses 25 mm top/left and 20 mm bottom/right margins; body is 12 pt Song with Times New Roman Latin, exact 20 pt lines and 24 pt first-line indent.
Keep V3Chapter/V3Heading2/V3Heading3 styles, black text, centered chapter titles, caption/figure pairing, repeating table headers, and Roman frontmatter plus Arabic body numbering.
Reconstruct the expandable body from complete V5 Markdown; preserve old scientific content and media while adding methods 3.6–3.7, protocol 4.4–4.5, results 5.10–5.13, system 6.6–6.7, updated bilingual abstracts/conclusion and an additional reproducibility appendix.
Date and subtitle may change; author and original title remain. Bibliography is renumbered by first appearance. No content controls, redlines or comments are used as source slots. Equations, cover artwork and existing figure source bytes are preserve-only.
New tables use existing caption/table/row components. The summary numeric table gets explicit wider numeric columns. No original file is overwritten.
Word must update TOC/page fields and export PDF. Render all final pages with bundled render_docx.py using Word's PDF, visually inspect them, check text/figures/tables/TOC, and correct layout before delivery.
''', encoding='utf-8')
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
