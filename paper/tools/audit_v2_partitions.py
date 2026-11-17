"""V2 retrospective audit. Reads original artifacts; writes only paper/ evidence."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
E=ROOT/'paper/evidence'
SOURCES={}
CLASSES=['N','V']

def src(name):
    p=ROOT/name
    SOURCES[name]={'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}
    return p
def table(name):
    return pd.read_csv(src(name),keep_default_na=False,low_memory=False,dtype={'record_id':str})
def obj(name):
    return json.loads(src(name).read_text(encoding='utf-8-sig'))
def records(d):
    return json.loads(d.to_json(orient='records',force_ascii=False,double_precision=15))
def write_json(value,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')

def score(d):
    cm=np.zeros((2,2),dtype=np.int64)
    for t,p in zip(d.true_aami_label,d.predicted_aami_label):cm[CLASSES.index(t),CLASSES.index(p)]+=1
    per={}
    for i,c in enumerate(CLASSES):
        tp=int(cm[i,i]);sup=int(cm[i].sum());pc=int(cm[:,i].sum())
        precision=tp/pc if pc else 0.; recall=tp/sup if sup else 0.
        per[c]={'support':sup,'predicted_count':pc,'precision':precision,'recall':recall,
                'f1':2*precision*recall/(precision+recall) if precision+recall else 0.}
    return {'accuracy':float(np.trace(cm)/cm.sum()),'macro_f1':float(np.mean([r['f1'] for r in per.values()])),
            'macro_precision':float(np.mean([r['precision'] for r in per.values()])),
            'macro_recall':float(np.mean([r['recall'] for r in per.values()])),
            'per_class':per,'confusion_matrix':cm.tolist(),'N_to_V':int(cm[0,1]),'V_to_N':int(cm[1,0]),'sample_count':len(d)}

def checkpoint_proof():
    """Read tensors/metadata only, no prediction or fitting. Run using project Python -B."""
    import torch
    bestpath='checkpoints/nv44_v1/formal/cnn/cnn_best.pt'
    finalpath='checkpoints/nv44_v1/formal/cnn/cnn_final_best.pt'
    a=torch.load(src(bestpath),map_location='cpu',weights_only=True)
    b=torch.load(src(finalpath),map_location='cpu',weights_only=True)
    same=set(a['state_dict'])==set(b['state_dict']) and all(torch.equal(a['state_dict'][k],b['state_dict'][k]) for k in a['state_dict'])
    assert same and b['class_names']==CLASSES and a['class_count']==2 and a['epoch']==b['best_epoch']==12
    proof={'operation':'read checkpoint tensors and metadata only, no inference/training',
           'torch_audit_runtime':torch.__version__,'best_metadata':{k:v for k,v in a.items() if k!='state_dict'},
           'final_metadata':{k:v for k,v in b.items() if k!='state_dict'},'same_state_dict_all_tensors':same,
           'tensor_shapes':{k:list(v.shape) for k,v in a['state_dict'].items()},'source_inventory':SOURCES.copy()}
    write_json(proof,E/'v2_nv_checkpoint_proof.json')
    print(json.dumps({k:v for k,v in proof.items() if k!='tensor_shapes'},ensure_ascii=False,indent=2))

def audit():
    E.mkdir(parents=True,exist_ok=True)
    output={'audit_time_Asia_Shanghai':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
            'scope':'Retrospective descriptive comparison of saved validation/test predictions; no new held-out experiment',
            'class_order':CLASSES,'partitions':{},'dataset_flow':[]}
    base='results/classification/nv44_v1'
    md=table('data/processed/mitdb44_nv_v1/metadata.csv')
    inc=md[md.included.eq(True)]
    cfg=obj(f'{base}/config.json')
    pcfg=obj('data/processed/mitdb44_nv_v1/processing_config.json')
    norm=obj('data/processed/mitdb44_nv_v1/normalization.json')
    ver=obj('data/processed/mitdb44_nv_v1/verification.json')
    manifest=table('data/processed/mitdb44_nv_v1/split_manifest.csv')
    assert manifest.record_id.nunique()==ver['included_record_count']==44 and manifest.subject_id.nunique()==ver['subject_count']==43
    training=obj('checkpoints/nv44_v1/formal/cnn/cnn_training_summary.json')
    hist=table('checkpoints/nv44_v1/formal/cnn/cnn_training_history.csv')
    proof=obj('paper/evidence/v2_nv_checkpoint_proof.json')
    assert cfg['class_names']==pcfg['classes']==proof['final_metadata']['class_names']==CLASSES
    assert cfg['class_ids']==pcfg['class_to_id']==ver['target_label_mapping']=={'N':0,'V':1}
    assert proof['final_metadata']['dataset_config_hash']==hashlib.sha256((ROOT/'data/processed/mitdb44_nv_v1/processing_config.json').read_bytes()).hexdigest()
    assert cfg['dataset_artifact_hashes']['processing_config_sha256']==proof['final_metadata']['dataset_config_hash']
    assert training['best_epoch']==proof['best_metadata']['epoch']==12
    assert abs(hist.loc[hist.epoch.eq(12),'val_macro_f1'].item()-training['best_val_macro_f1'])<1e-12
    patient_rows=[]
    for split in ('val','test'):
        name=f'{base}/{split}_predictions_cnn_1d.csv'
        d=table(name); saved=obj(f'{base}/{split}_metrics_cnn_1d.json')
        m=inc[inc.split.eq(split)].set_index('sample_id').loc[d.sample_id]
        assert set(d.split)=={split} and set(d.model)=={'cnn_1d'} and d.sample_id.nunique()==len(d)
        assert list(d.true_aami_label)==list(m.mapped_label) and list(d.original_label)==list(m.original_label)
        assert list(d.original_label.map(pcfg['full_aami_mapping']))==list(d.true_aami_label)
        assert list(d.subject_id)==list(m.subject_id) and list(d.annotation_sample)==list(m.annotation_sample)
        probabilities=d[['probability_N','probability_V']].to_numpy(float)
        assert np.isfinite(probabilities).all() and np.max(np.abs(probabilities.sum(1)-1))<1e-6
        assert np.array_equal(np.asarray(CLASSES)[probabilities.argmax(1)],d.predicted_aami_label.to_numpy())
        values=score(d)
        for k in ['accuracy','macro_f1','macro_precision','macro_recall']:
            assert abs(values[k]-saved[k])<1e-12,(split,k)
        for c in CLASSES:
            for k in ['precision','recall','f1','support']:
                assert abs(values['per_class'][c][k]-saved['per_class'][c][k])<1e-12
        assert values['confusion_matrix']==saved['confusion_matrix']
        vc=d[d.true_aami_label.eq('V')].groupby('subject_id').size().sort_values(ascending=False)
        fractions=vc/vc.sum()
        values.update({'subjects_total':d.subject_id.nunique(),'records_total':d.record_id.nunique(),
            'subjects_with_V':len(vc),'V_subject_coverage_pct':len(vc)/d.subject_id.nunique()*100,
            'V_subject_counts':{k:int(v) for k,v in vc.items()},'V_subject_shares_pct':{k:float(v*100) for k,v in fractions.items()},
            'top_V_subject':str(vc.index[0]),'top_V_subject_count':int(vc.iloc[0]),'top_V_subject_share_pct':float(fractions.iloc[0]*100),
            'top2_V_share_pct':float(fractions.head(2).sum()*100),'top3_V_share_pct':float(fractions.head(3).sum()*100),
            'V_subject_HHI':float(np.square(fractions).sum()),'V_effective_subject_count_entropy':float(2**(-(fractions*np.log2(fractions)).sum())),
            'subjects':sorted(d.subject_id.unique()),'prediction_source':name,'saved_json_match':True,
            'class_order_argmax_match':True,'metadata_labels_positions_match':True,
            'original_symbol_counts':records(d.groupby(['original_label','true_aami_label']).size().rename('count').reset_index())})
        values['patient_metrics']=[]
        for subject,g in d.groupby('subject_id',sort=True):
            v=score(g)
            present=[c for c in CLASSES if v['per_class'][c]['support']>0]
            row={'split':split,'subject_id':subject,'records':';'.join(sorted(g.record_id.unique())),
                'sample_count':len(g),'accuracy':v['accuracy'],'macro_f1_fixed_NV':v['macro_f1'],
                'macro_f1_present_true_classes':float(np.mean([v['per_class'][c]['f1'] for c in present])),
                'N_to_V':v['N_to_V'],'V_to_N':v['V_to_N'],
                'V_share_of_partition_V_pct':v['per_class']['V']['support']/values['per_class']['V']['support']*100,
                'N_to_V_share_of_partition_N_to_V_pct':v['N_to_V']/values['N_to_V']*100 if values['N_to_V'] else 0.,
                'source':name}
            for c in CLASSES:
                r=v['per_class'][c]
                for k in ['support','predicted_count','precision','f1']:row[f'{c}_{k}']=r[k]
                row[f'{c}_recall']=r['recall'] if r['support'] else None
            values['patient_metrics'].append(row);patient_rows.append(row)
        output['partitions'][split]=values
    output['consistency_audit']={
        'label_definition':'same explicit AAMI N={N,L,R,e,j}, V={V,E}; CSV labels rejoined to unchanged metadata',
        'class_order':'N=0,V=1 in dataset/model config, checkpoint and probability columns; every CSV argmax agrees',
        'metric_function':'src/classify.py run_formal uses score_predictions for both, with fixed [0,1], macro average, zero_division=0; independent CSV recomputation matches each JSON',
        'preprocessing':'same mitdb44_nv_v1 preprocessing config and normalization.json across train/val/test; metadata MLII/360Hz/253-point centers align; prior audit checked NPZ normalized inputs',
        'model_version':'cnn_best.pt and cnn_final_best.pt have identical state_dict, epoch12; class_names N,V; saved dataset hash agrees; src/classify.py creates both CSVs from same returned best cnn',
        'checkpoint_proof':proof,
        'historical_binding_limit':'CSV has no checkpoint hash or immutable source-code commit. Source, matching summary/epoch and current equal checkpoint tensors support consistency, but this audit does not reconstruct historical process or rerun model inference; cannot prove original runtime identity solely cryptographically.',
        'not_determined':['No causal test isolates patient morphology, noise, record gain, annotation heterogeneity, or optimization contributions.',
                          'A validation/test gap alone does not establish overfitting, data leakage, or temporal model degradation.',
                          'No patient-independent external dataset, newly blinded holdout, repeated seed experiment, or calibrated clinical endpoint was added.']}
    for p in ['src/classify.py','src/evaluation/metrics.py','src/training/trainer.py','src/models/classifiers.py',
              'src/labels.py','src/datasets/build.py','src/preprocessing/extraction.py','src/preprocessing/normalization.py','src/preprocessing/filters.py']:
        src(p)
    # Raw annotation counts are read directly; no unknown intermediate is inferred.
    all48=table('results/classification/dataset/raw_symbol_counts_all48.csv')
    byrec48=table('results/classification/dataset/raw_symbol_counts_by_record_all48.csv')
    raw44=table('results/classification/dataset/raw_symbol_counts_44.csv')
    aami44=table('results/classification/dataset/aami_counts_44.csv')
    assert len(byrec48.record_id.unique())==48
    agg=byrec48.groupby('symbol')['count'].sum().to_dict()
    assert agg==all48.set_index('symbol')['count'].to_dict()
    include44=byrec48[byrec48.included_in_44_record_experiment.eq(True)]
    assert include44.record_id.nunique()==44
    assert include44.groupby('symbol')['count'].sum().to_dict()==raw44.set_index('symbol')['count'].to_dict()
    assert set(byrec48.record_id)-set(include44.record_id)=={'102','104','107','217'}
    assert raw44[raw44.aami_group.ne('')].groupby('aami_group')['count'].sum().to_dict()==aami44.set_index('aami_group')['count'].to_dict()
    assert len(md)==int(raw44['count'].sum())
    flow=[]
    def flowrow(stage,scope,count,unit,source,definition,verified='是',note=''):
        flow.append({'阶段':stage,'范围':scope,'数量':count,'单位':unit,'来源文件':source,'统计定义':definition,'是否核验':verified,'备注':note})
    flowrow('原始记录','MIT-BIH全库',48,'条','results/classification/dataset/raw_symbol_counts_by_record_all48.csv','逐record_id去重')
    flowrow('排除含起搏心拍记录','正式实验',4,'条','data/processed/mitdb44_nv_v1/processing_config.json','102、104、107、217')
    flowrow('保留记录','正式实验',44,'条','data/processed/mitdb44_nv_v1/verification.json','记录选择后；201/202合并为一个受试者组')
    flowrow('保留受试者组','正式实验',43,'组','data/processed/mitdb44_nv_v1/split_manifest.csv','患者组计数，不是心拍计数')
    flowrow('全部原始注释事件','48记录',int(all48['count'].sum()),'条','results/classification/dataset/raw_symbol_counts_all48.csv','包括心拍、节律、质量、注释等，不可命名为心拍数')
    flowrow('AAMI映射心拍','48记录',int(all48.loc[all48.aami_label.ne(''),'count'].sum()),'拍','results/classification/dataset/raw_symbol_counts_all48.csv','显式N/S/V/F/Q映射所覆盖的逐拍符号；不是全部注释事件')
    flowrow('全部原始注释事件','44记录',int(raw44['count'].sum()),'条','results/classification/dataset/raw_symbol_counts_44.csv','与metadata行数和record_checks.annotation_count合计一致')
    flowrow('AAMI映射心拍','44记录',int(aami44['count'].sum()),'拍','results/classification/dataset/aami_counts_44.csv','N/S/V/F/Q五组计数合计')
    output['raw_counts']={'all48_annotation_events':int(all48['count'].sum()),'all48_AAMI_mapped_beats':int(all48.loc[all48.aami_label.ne(''),'count'].sum()),
                          'records44_annotation_events':int(raw44['count'].sum()),'records44_AAMI_mapped_beats':int(aami44['count'].sum()),
                          'records44_AAMI_pre_window':{r.aami_group:int(r['count']) for _,r in aami44.iterrows()}}
    output['task_construction']={}
    for task in ['nv','nsvf']:
        bn=f'data/processed/mitdb44_{task}_v1'
        m=md if task=='nv' else table(f'{bn}/metadata.csv')
        v=ver if task=='nv' else obj(f'{bn}/verification.json')
        rc=table(f'{bn}/record_checks.csv')
        exclusions=table(f'{bn}/exclusion_counts.csv')
        target=m[m.is_target.eq(True)];accepted=m[m.included.eq(True)]
        assert int(rc.annotation_count.sum())==len(m)==int(raw44['count'].sum())
        assert int(rc.included_samples.sum())==len(accepted)
        assert len(m[m.annotation_kind.eq('mapped_beat')])==int(aami44['count'].sum())
        fail=target[~target.included.eq(True)].groupby('exclusion_reason').size().to_dict()
        assert sum(fail.values())+len(accepted)==len(target)
        assert (exclusions.set_index(['split','exclusion_reason'])['count'].to_dict()==m.groupby(['split','exclusion_reason']).size().to_dict())
        t=task.upper() if task=='nv' else 'N/S/V/F'
        flowrow('标签筛选后目标心拍',t,len(target),'拍',f'{bn}/metadata.csv','is_target=True；在技术窗口排除之前')
        for reason,n in sorted(fail.items()):
            flowrow('目标心拍技术排除 '+reason,t,int(n),'拍',f'{bn}/metadata.csv','仅在is_target=True中统计，各排除原因互斥')
        flowrow('最终有效窗口',t,len(accepted),'拍',f'{bn}/metadata.csv','included=True；并与record_checks和verification验证',note='每拍253点，非253个独立样本')
        output['task_construction'][task]={'mapped_target_before_technical_exclusion':len(target),'technical_exclusion_counts':{k:int(v) for k,v in fail.items()},
            'valid_windows':len(accepted),'per_class_before':{k:int(v) for k,v in target.groupby('mapped_label').size().items()},
            'per_class_after':{k:int(v) for k,v in accepted.groupby('mapped_label').size().items()},
            'source':f'{bn}/metadata.csv'}
    output['dataset_flow']=flow
    output['count_definition_limit']='No single ambiguous “all original beats” count is substituted for annotation events. 109494/100733 explicitly count symbols covered by the project AAMI mapping; nonbeat events are excluded by definition, not guessed.'
    output['source_inventory']=SOURCES.copy()
    write_json(output,E/'v2_nv_partition_comparison.json')
    pd.DataFrame(patient_rows).to_csv(E/'v2_nv_patient_metrics.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(flow).to_csv(E/'v2_dataset_flow.csv',index=False,encoding='utf-8-sig')
    write_claims(output)
    write_discussion(output)
    write_report(output)
    print(json.dumps({'passed':True,'partitions':{k:{x:v[x] for x in ['accuracy','macro_f1','N_to_V','V_to_N','subjects_with_V','top_V_subject','top_V_subject_share_pct']} for k,v in output['partitions'].items()},'flow':output['task_construction']},ensure_ascii=False,indent=2))
    return output

def write_claims(o):
    cols=['论文位置','结论文本','指标或数据','来源文件','表格或图像路径','是否核验','备注']
    rows=[]
    def add(loc,claim,val,source,view='',note='V2回顾性复算；未训练、未改分区、未选择新模型'):
        rows.append(dict(zip(cols,[loc,claim,val,source,view,'是',note])))
    for split,v in o['partitions'].items():
        name=v['prediction_source']
        for k in ['accuracy','macro_f1','N_to_V','V_to_N','subjects_with_V','top_V_subject_share_pct']:
            add('5.1 验证与测试差异',f'N/V CNN {split} {k}',v[k],name,'验证与测试分区对比图')
        for c,r in v['per_class'].items():
            for k in ['support','precision','recall','f1']:
                add('5.1 验证与测试差异',f'N/V CNN {split} {c} {k}',r[k],name,'验证测试逐类指标表')
    p=next(r for r in o['partitions']['val']['patient_metrics'] if r['subject_id']=='subject_109')
    add('5.1 验证与测试差异','验证N→V错误集中于subject_109',f"{p['N_to_V']}/2511={p['N_to_V_share_of_partition_N_to_V_pct']:.6f}%",p['source'],'验证与测试分区对比图')
    add('5.1 验证与测试差异','当前最佳与最终最佳检查点张量一致','epoch12, state_dict all equal','paper/evidence/v2_nv_checkpoint_proof.json','',note='只读模型；CSV无模型SHA，历史绑定限制见审计')
    for r in o['dataset_flow']:
        add('2.1 数据构建统计',r['阶段']+' '+r['范围'],str(r['数量'])+r['单位'],r['来源文件'],'数据构建统计表',r['统计定义'])
    for r in [*o['partitions']['val']['patient_metrics'],*o['partitions']['test']['patient_metrics']]:
        add('5.1 验证与测试差异',r['split']+' '+r['subject_id']+' 患者级分类表现',
            f"n={r['sample_count']};N={r['N_support']};V={r['V_support']};acc={r['accuracy']};N_to_V={r['N_to_V']};V_to_N={r['V_to_N']}",
            r['source'],'paper/evidence/v2_nv_patient_metrics.csv',note='患者级Accuracy按该患者心拍；无真实V时V Recall留空')
    pd.DataFrame(rows,columns=cols).to_csv(E/'claim_evidence_v2_nv.csv',index=False,encoding='utf-8-sig')

def write_discussion(o):
    text='''### 验证集与测试集结果差异讨论

为分析N/V CNN验证Macro-F1为0.6630、测试为0.9865的差异，本文回顾既有两份逐拍预测，并核对标签、模型与计算约定。两者均采用N=0、V=1的类别顺序、相同AAMI映射和固定二类Macro-F1；预处理配置及训练集归一化参数一致。训练记录与检查点均指向第12轮，当前最佳与最终最佳检查点的全部参数张量一致，生成程序也对同一最佳模型对象分别保存验证和测试预测。CSV未记录检查点哈希，因此这些交叉证据支持结果可比，但不能仅据文件完全重建历史运行过程。

验证集包含11854拍N、1069拍V，测试集分别为12287和1161拍，V占比约8.27%与8.63%，这一接近的频率不足以解释指标差距。验证V的Precision为0.2905、Recall为0.9616、F1为0.4462；测试相应为0.9607、0.9905和0.9754。主要差别是验证N→V为2511拍，而测试仅47拍；验证与测试V→N分别为41与11拍。验证N→V中2477拍来自患者109，占98.65%；该患者2478拍N仅1拍判对，其他验证患者未呈现同等规模的误报。因此较低验证分数具有明确的患者集中现象，不能笼统归因为V类召回不足。

两分区各有6个患者组，但有真实V的患者分别为4与5个；验证V的77.17%来自患者233，测试V的84.84%来自患者208。大量相关心拍会提高某一患者对按拍汇总指标的影响，且V支持仅1拍或3拍的患者不能提供稳定的逐患者召回估计。上述统计说明患者组成需要纳入差异解释，尚不能证明记录109的具体失误由何种形态、噪声或模型机制引起，也不能据分数反差直接认定过拟合、数据泄漏或模型随时间退化。本分析未改变阈值、模型或划分，属于已存在数据的回顾性诊断，仍需新的患者来源和独立验证检验稳定性。
'''
    p=ROOT/'paper/draft/v2_nv_discussion.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf-8')

def write_report(o):
    lines=['# V2 N/V验证测试分区审计','',f"核验时间：{o['audit_time_Asia_Shanghai']}",'',
    '## 结论','',
    '0.6630与0.9865分别从既有val/test CNN逐拍预测复算得到，均与保存JSON、训练最佳验证记录吻合。主要可观测差别是验证N→V误报集中在患者109，不是简单的V比例差异或V召回失败；不能由分数差直接认定过拟合、泄漏或退化。','',
    '本次不训练、不改变阈值、不重选检查点、不改数据/划分/预测；只读检查点张量，不重新运行模型推理。新增文件全部位于paper。','',
    '## 同源与可比性核对','',
    '| 项目 | 核对结果 | 证据 |','|---|---|---|',
    '| 标签 | 相同N={N,L,R,e,j}、V={V,E}，并逐ID核对CSV真值/原符号/位置与metadata | src/labels.py；metadata.csv；两份预测CSV |',
    '| 类序 | dataset、run config、checkpoint均N=0,V=1；每行概率argmax等于标签 | processing_config.json；config.json；checkpoint proof |',
    '| 指标 | 同一score_predictions，固定两类宏平均、zero_division=0；本次独立从混淆矩阵复算 | src/evaluation/metrics.py；src/classify.py；val/test_metrics_cnn_1d.json |',
    '| 预处理 | 相同MLII、360Hz、253点、离线滤波配置；共享训练拟合normalization | processing_config.json；normalization.json；既有NPZ审计 |',
    '| 检查点 | epoch12最佳；cnn_best与cnn_final_best全部state_dict相同；数据config哈希匹配 | v2_nv_checkpoint_proof.json；cnn_training_history.csv |',
    '| 保存流程 | run_formal对同一returned best cnn调用predict_cnn生成val/test，再用同metric函数 | src/classify.py；src/training/trainer.py |','',
    '**不可完全确认的历史绑定：**CSV没有检查点SHA或代码commit字段。当前检查点、配置、epoch、最佳验证分数与源代码相互吻合，但此次未重建历史进程、未重新推理，不能给出两份CSV历史生成时runtime完全一致的密码学证明。无矛盾证据不等于证明任何可能泄漏绝不存在。','',
    '## 分区总体与逐类表现','',
    '| 分区 | 拍数 | N/V | V占比% | Accuracy | Macro-F1 | N→V | V→N |','|---|---:|---|---:|---:|---:|---:|---:|']
    for s,v in o['partitions'].items():
        p=v['per_class'];lines.append(f"| {s} | {v['sample_count']} | {p['N']['support']}/{p['V']['support']} | {p['V']['support']/v['sample_count']*100:.4f} | {v['accuracy']:.6f} | {v['macro_f1']:.6f} | {v['N_to_V']} | {v['V_to_N']} |")
    lines+=['','| 分区 | 类别 | Precision | Recall | F1 | 支持 |','|---|---|---:|---:|---:|---:|']
    for s,v in o['partitions'].items():
        for c,r in v['per_class'].items():lines.append(f"| {s} | {c} | {r['precision']:.6f} | {r['recall']:.6f} | {r['f1']:.6f} | {r['support']} |")
    lines+=['','## 患者构成与集中度','','| 分区 | 总患者 | 有V患者 | 最大V来源 | V拍数/该分区V | 份额% | 熵有效V来源患者数 |','|---|---:|---:|---|---|---:|---:|']
    for s,v in o['partitions'].items():
        lines.append(f"| {s} | {v['subjects_total']} | {v['subjects_with_V']} | {v['top_V_subject']} | {v['top_V_subject_count']}/{v['per_class']['V']['support']} | {v['top_V_subject_share_pct']:.4f} | {v['V_effective_subject_count_entropy']:.4f} |")
    lines+=['','熵有效患者数只描述心拍来源集中，不是独立样本数量或临床患者数。','',
    '| 分区/患者 | N支持 | V支持 | Accuracy | N→V | V→N | N Recall | V Recall |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for s,v in o['partitions'].items():
        for r in v['patient_metrics']:
            nr='—' if r['N_recall'] is None else f"{r['N_recall']:.6f}";vr='—' if r['V_recall'] is None else f"{r['V_recall']:.6f}"
            lines.append(f"| {s}/{r['subject_id']} | {r['N_support']} | {r['V_support']} | {r['accuracy']:.6f} | {r['N_to_V']} | {r['V_to_N']} | {nr} | {vr} |")
    lines+=['','患者CSV同时保留固定N/V Macro-F1和仅真实出现类的Macro-F1，两者不能混用；无真实V患者V Recall为空，不以0冒充可估计的召回。只有1或3拍V时，即使Recall为1也不能解释为稳定估计。','',
    '验证患者109的N→V=2477，占验证全部2511次N误报的98.65%；该患者N支持2478，N召回约0.000404。验证大多数N误报有明确的患者集中现象。测试V主要来自208，验证V主要来自233，即使二者类别份额相近，也不代表患者形态分布相同。形态、信噪比、增益、标签异质性或优化机制各自贡献未做因果隔离，不能断言模型记住患者身份或学到特定病理特征。','',
    '## 数据构建数量流程','',
    '完整表见v2_dataset_flow.csv。原始注释事件、项目映射心拍与技术合格窗口严格分开；以下不是按差额猜算，均分别从源表/metadata直接计数，并与记录检查合计核对。','',
    '| 阶段 | 范围 | 数量 | 单位 |','|---|---|---:|---|']
    for r in o['dataset_flow']:lines.append(f"| {r['阶段']} | {r['范围']} | {r['数量']} | {r['单位']} |")
    lines+=['','44记录映射前窗口计数N=90125、S=2781、V=7009、F=803、Q=15。NV目标97134经filter_edge_or_gap_guard 540与window_boundary 40排除，保留96554；四类目标100718经对应562与41排除，保留100115。不存在的“单独去噪后拍数”等中间统计不补造。','',
    '48记录的109494是显式AAMI逐拍符号总量，而112647是全部注释事件；44记录对应100733与103724。论文应将前者命名为“项目AAMI映射心拍”，避免把未映射事件自动断定为其他临床心拍。','',
    '## 来源及复查','',
    '数值与逐源SHA-256见v2_nv_partition_comparison.json；患者明细见v2_nv_patient_metrics.csv；构建流见v2_dataset_flow.csv；新增中文证据行见claim_evidence_v2_nv.csv。','',
    '复查只读检查点：`.venv/Scripts/python.exe -B paper/tools/audit_v2_partitions.py --checkpoint-proof`；之后使用捆绑Python执行`paper/tools/audit_v2_partitions.py`。脚本只写paper，不训练。']
    p=ROOT/'paper/review/nv_partition_audit.md';p.parent.mkdir(parents=True,exist_ok=True);p.write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--checkpoint-proof',action='store_true');args=parser.parse_args()
    if args.checkpoint_proof:checkpoint_proof()
    else:audit()
