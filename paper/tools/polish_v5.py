"""Humanizer-zh: local prose edits to V4; preserve claims and Word objects."""
from pathlib import Path
import importlib.util
import json
import re

ROOT = Path(__file__).resolve().parents[2]
FRAGMENTS = [
('本文围绕心电图标注心拍分类和课程实验展示，使用MIT-BIH心律失常数据库比较逻辑回归、随机森林与一维卷积神经网络，并开发ECG-AI可视化系统。', '本文使用MIT-BIH心律失常数据库比较逻辑回归、随机森林与一维卷积神经网络，开展标注心拍分类实验，并开发用于课程展示的ECG-AI可视化系统。'),
('重新推理及标签、数据对应检查支持原结果复现', '重新推理并核对标签与数据的对应关系，支持原结果复现'),
('新策略没有使S、F同时改善，本文保留了指标上升和漏检增加的结果。', '新策略未能同时改善S、F识别，本文一并报告指标上升与漏检增加的结果。'),
('课程系统将真实心拍、专家标签、预测分数和错误案例对应展示，学生可以据此理解指标，并判断实验结论适用于哪些数据条件。', '课程系统对应展示真实心拍、专家标签、预测分数和错误案例，帮助学生理解指标及实验结论适用的数据条件。'),
('两者对应不同输入信息。', '两者提供不同的输入信息。'),
('类别不平衡和患者划分都会影响心拍分类评价。', '心拍分类的评价结果同时受类别不平衡和患者划分影响。'),
('该评价采用不同记录集合，患者互斥性仍需额外核查。', '该评价使用不同的记录集合，但仍需另行核查患者是否互斥。'),
('本文建立可追溯的心拍分类实验和展示流程，比较三种模型在相同N/V任务上的表现，并考察任务扩展为四分类后各类别的变化。', '本文建立可追溯的心拍分类实验与展示流程，在相同N/V任务上比较三种模型，再考察扩展为四分类后各类别的表现变化。'),
('模型结果表只统计满足窗口与信号有效性规则、实际进入数据集的心拍，数据构建表另列原始事件和映射阶段的数量。', '模型结果表只统计符合窗口和信号有效性规则、实际进入数据集的心拍；原始事件数与标签映射阶段的数量另列于数据构建表。'),
('比较结果说明各方案在当前输入条件下的表现，不能将全部差异归因于某个网络组件。', '这些比较反映各方案在当前输入条件下的表现，不能把全部差异归因于某个网络组件。'),
('正式配置包含100棵树，最大深度为18，每个叶节点至少含2个样本。', '正式配置使用100棵树，最大深度为18，每个叶节点至少包含2个样本。'),
('图3-1和表3-1依据项目中的模型定义整理，与本实验实际结构对应。', '图3-1和表3-1按项目中的模型定义整理，对应本实验实际使用的结构。'),
('该目标调整不同标签在损失中的相对贡献，不等于增加少数类患者。', '该训练目标调整各标签对损失的相对贡献，并未增加少数类患者。'),
('RR方案同时增加时间信息和可训练分支，本实验比较的是这一组合，不能将差异全部归因于单个特征。', 'RR方案同时加入时间信息和可训练分支，因此本实验比较的是两者的组合，不能把差异全部归因于单个特征。'),
('Accuracy按心拍计数，容易受到多数类影响。', 'Accuracy按心拍计数，容易受多数类占比影响。'),
('CNN的优势随任务变化，二分类表现不能直接说明其多类识别能力。', 'CNN的优势随任务而变，其二分类表现不能直接说明多类识别能力。'),
('这个差异只表示当前固定分区的观察结果。', '这一差异仅是当前固定分区下的观察结果。'),
('较低验证分数主要表现为误报向个别患者集中，不能简单归因于V类召回不足。', '验证分数较低主要表现为误报集中于个别患者，不能简单归因于V类召回不足。'),
('数百拍F测试结果主要反映单个患者的心拍形态', '数百拍F的测试结果主要反映单个患者的心拍形态'),
('模型找回了更多少数类心拍，也产生了更多错误预测，权重调整没有使所有指标同时改善。', '模型找回更多少数类心拍的同时，也增加了错误预测；权重调整未能使所有指标同时改善。'),
('F1属于非线性汇总，各折的支持数和类别构成也不同，因此五折均值与合并全部折外预测后的Macro-F1并不相同。', 'F1是非线性指标，各折的支持数与类别构成也不同，因此五折均值不等于合并全部折外预测后计算的Macro-F1。'),
('患者来源集中时，大量相关心拍不能等同于大量独立患者证据。', '患者来源集中时，大量相关心拍不能视为大量独立患者证据。'),
('相邻方案分别比较权重平滑、Focal调制和RR分支组合', '相邻方案分别对照权重平滑、Focal调制和RR分支组合'),
('新增对照只能比较当前固定条件下的训练策略，不能证明少数类的临床泛化问题已经解决。', '新增对照仅比较当前固定条件下的训练策略，不能证明少数类的临床泛化问题已得到解决。'),
('解释模型来自验证选定的focal_sqrt_rr方案', '用于归因的模型来自验证选定的focal_sqrt_rr方案'),
('RR方案还包含波形以外的输入，单看波形归因不能解释全部决策。', 'RR方案还使用波形以外的输入，仅看波形归因无法解释全部决策。'),
('科研结果展示和单次请求内的模型推理使用不同数据路径。', '科研结果展示与单次请求中的模型推理使用不同的数据路径。'),
('图6-1区分请求调用、标准化输入和文件读取。', '图6-1分别展示请求调用、标准化输入和文件读取。'),
('该流程仍以专家标注中心为前提', '该流程仍以专家标注位置为中心'),
('六个模型未全部就绪时，健康接口返回503。', '六个模型尚未全部就绪时，健康接口返回503。'),
('这些检查说明软件按预期读取和展示数据，不代表已经验证医学泛化或教学效果。', '这些检查验证软件能否按预期读取和展示数据，不能据此认定其医学泛化能力或教学效果已获验证。'),
('同一患者的大量相关心拍不能替代独立患者证据。', '同一患者的大量相关心拍不能替代独立患者证据。'),
('后续研究需要在新增患者数据上预先冻结评价方案，分别考察自动R峰定位和节律上下文的贡献，再评价模型部署与概率校准。', '后续研究需面向新增患者数据预先冻结评价方案，分别考察自动R峰定位与节律上下文的贡献，再评价模型部署和概率校准。'),
]


def main():
    spec = importlib.util.spec_from_file_location('v4_editor', Path(__file__).with_name('polish_v4.py'))
    editor = importlib.util.module_from_spec(spec); spec.loader.exec_module(editor)
    editor.SOURCE = ROOT / 'paper/draft/ECG_AI_课程论文_语言润色版V4.md'
    editor.TARGET = ROOT / 'paper/draft/ECG_AI_课程论文_自然表达版V5.md'
    editor.DOCX3 = ROOT / 'paper/final/ECG_AI_课程论文_语言润色版V4.docx'
    editor.DOCX4 = ROOT / 'paper/final/ECG_AI_课程论文_自然表达版V5.docx'
    editor.QA = ROOT / 'paper/qa/v5'
    lines = editor.SOURCE.read_text(encoding='utf-8').splitlines()
    changes = {}
    for before, after in FRAGMENTS:
        if before == after:
            continue
        hits = [i for i, line in enumerate(lines) if before in line]
        assert len(hits) == 1, (before, hits)
        i = hits[0]
        assert not lines[i].startswith(('#', '|', '$$', '![', '['))
        changes[i] = changes.get(i, lines[i]).replace(before, after)
    editor.EDITS = [(lines[i], changes[i]) for i in sorted(changes)]
    editor.make_draft()
    path = editor.QA / 'language_revision_manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    manifest.update(scope='humanizer-zh: Chinese prose only; retain claims, scope and uncertainty',
                    skill='humanizer-zh', date_Asia_Shanghai='2026-11-19')
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    editor.make_docx()
    from docx import Document
    document = Document(editor.DOCX4)
    document.core_properties.subject = '医学人工智能课程论文，自然表达版V5'
    document.save(editor.DOCX4)


if __name__ == '__main__':
    main()
