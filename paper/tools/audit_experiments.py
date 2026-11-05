"""Read existing artifacts; recompute paper evidence without fitting any model."""
from __future__ import annotations
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'paper/evidence'
MODELS = ('logistic_regression', 'random_forest', 'cnn_1d')
SOURCES = {}

def source(p):
    p = ROOT / p if not isinstance(p, Path) else p
    key = p.relative_to(ROOT).as_posix()
    SOURCES[key] = {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
    return p

def load(p):
    return json.loads(source(p).read_text(encoding='utf-8-sig'))

def frame(p):
    return pd.read_csv(source(p), keep_default_na=False, dtype={'record_id':str}, low_memory=False)

def metrics(d, classes, truth='true_aami_label', pred='predicted_aami_label'):
    cm = np.zeros((len(classes), len(classes)), dtype=np.int64)
    for a,b in zip(d[truth],d[pred]):
        cm[classes.index(a), classes.index(b)] += 1
    per = {}
    for i,c in enumerate(classes):
        tp = int(cm[i,i]); sup = int(cm[i,:].sum()); pc = int(cm[:,i].sum())
        pr = tp / pc if pc else 0.; re = tp / sup if sup else 0.
        per[c] = {'precision': pr, 'recall':re,'f1': 2*pr*re/(pr+re) if pr+re else 0.,
                  'support':sup,'predicted_count':pc,'predicted_share_pct':pc/len(d)*100}
    return {'accuracy':float(np.trace(cm)/cm.sum()), 'macro_f1':float(np.mean([r['f1'] for r in per.values()])),
            'macro_precision':float(np.mean([r['precision'] for r in per.values()])),
            'macro_recall':float(np.mean([r['recall'] for r in per.values()])),
            'per_class':per,'confusion_matrix':cm.tolist(),'sample_count':len(d)}

def exact_metric_match(a,b):
    for k in ('accuracy','macro_f1'):
        assert abs(a[k]-b[k])<1e-12,(k,a[k],b[k])
    if 'confusion_matrix' in b:
        assert a['confusion_matrix']==b['confusion_matrix']
    for c,r in a['per_class'].items():
        if 'per_class' in b:
            for k in ('precision','recall','f1','support'):
                assert abs(r[k]-b['per_class'][c][k])<1e-12,(c,k)

def records(d):
    return json.loads(d.to_json(orient='records',force_ascii=False))

def audit():
    OUT.mkdir(parents=True,exist_ok=True)
    evidence = {'verified_at_Asia_Shanghai':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
                'scope':'Read-only audit of saved experimental artifacts; no fitting or model selection',
                'datasets':{},'test_metrics':{},'cnn_training':{},'error_examples':{}}
    metadata = {}
    for task,classes in (('nv',['N','V']),('nsvf',['N','S','V','F'])):
        base = f'data/processed/mitdb44_{task}_v1'
        m = frame(f'{base}/metadata.csv')
        m = m[m.included.eq(True)].copy()
        metadata[task] = m
        cfg = load(f'{base}/processing_config.json')
        plan = load(f'{base}/split_plan.json')
        norm = load(f'{base}/normalization.json')
        manifest = frame(f'{base}/split_manifest.csv')
        assert manifest.subject_id.nunique()==43 and len(manifest)==44
        assert set(manifest.loc[manifest.record_id.isin(['201','202']),'subject_id'])=={'subject_201_202'}
        assert manifest[manifest.record_id.isin(['201','202'])].split.nunique()==1
        assert set(cfg['excluded_paced_records'])=={'102','104','107','217'}
        assert not set(manifest.record_id)&{'102','104','107','217'}
        assert set(m.lead)=={'MLII'} and set(m.fs_hz)=={360} and set(m.window_length)=={253}
        assert set(m.center_index)=={108} and m.sample_id.nunique()==len(m)
        assert set(m.unit)=={'mV'}
        assert (m.window_start_sample==m.annotation_sample-108).all()
        assert (m.window_stop_sample_exclusive==m.annotation_sample+145).all()
        stats = []
        class_coverage = []
        subjects = {}
        for split in ('train','val','test'):
            d=m[m.split.eq(split)]
            subjects[split]=set(d.subject_id)
            row={'split':split,'sample_count':len(d),'subject_count':d.subject_id.nunique(),'record_count':d.record_id.nunique()}
            row.update({c:int(d.mapped_label.eq(c).sum()) for c in classes})
            stats.append(row)
            # Arrays are read only for alignment and preprocessing verification, never training.
            with np.load(ROOT/f'{base}/{split}.npz', allow_pickle=False) as z:
                ordered=d.sort_values('npz_row')
                assert list(z['sample_id'])==list(ordered.sample_id)
                assert list(z['mapped_label'])==list(ordered.mapped_label)
                assert list(z['subject_id'])==list(ordered.subject_id)
                assert np.array_equal(z['y'],ordered.target_label.to_numpy())
                x=z['X']; xf=z['X_filtered']
                assert x.shape==(len(d),1,253) and np.isfinite(x).all()
                assert np.allclose(x,((xf.astype(np.float64)-norm['mean_mV'])/norm['std_mV']).astype(np.float32),atol=1e-6,rtol=1e-6)
                if split=='train':
                    assert abs(xf.astype(np.float64).mean()-norm['mean_mV'])<1e-12
                    assert abs(xf.astype(np.float64).std()-norm['std_mV'])<1e-12
            for c in classes:
                cc=d[d.mapped_label.eq(c)]
                ss=cc.groupby('subject_id').size().sort_values(ascending=False)
                class_coverage.append({'split':split,'class':c,'sample_count':len(cc),
                    'subjects_with_class':cc.subject_id.nunique(),'records_with_class':cc.record_id.nunique(),
                    'subjects_total':d.subject_id.nunique(),'top_subject':ss.index[0],
                    'top_subject_samples':int(ss.iloc[0]),'top_subject_share_pct':float(ss.iloc[0]/len(cc)*100)})
        assert not (subjects['train']&subjects['val'] or subjects['train']&subjects['test'] or subjects['val']&subjects['test'])
        # Corrected class-specific support fields must agree with independent metadata counts.
        sc=frame(f'{base}/split_class_counts.csv')
        for r in class_coverage:
            saved=sc[sc.split.eq(r['split'])&sc.aami_label.eq(r['class'])].iloc[0]
            assert saved.sample_count==r['sample_count'] and saved.subject_count==r['subjects_with_class'] and saved.record_count==r['records_with_class']
        allclass=[]
        for c in classes:
            cc=m[m.mapped_label.eq(c)]; ss=cc.groupby('subject_id').size().sort_values(ascending=False)
            allclass.append({'class':c,'samples':len(cc),'share_pct':len(cc)/len(m)*100,'subjects':cc.subject_id.nunique(),
                             'top_subject':ss.index[0],'top_subject_samples':int(ss.iloc[0]),'top_subject_share_pct':float(ss.iloc[0]/len(cc)*100)})
        evidence['datasets'][task]={'classes':classes,'splits':stats,'overall_class_counts':allclass,'class_subject_coverage':class_coverage,
                                  'subject_overlap':0,'records':44,'subjects':43,'config':cfg,'normalization':norm,
                                  'split_protocol':plan['protocol'],'test_subjects':sorted(subjects['test']),
                                  'verification':'metadata recomputation and every NPZ row/label/shape/normalization checked'}
        evidence['test_metrics'][task]={}
        for model in MODELS:
            result=f'results/classification/{task}44_v1'
            predfile=f'{result}/test_predictions_{model}.csv'
            d=frame(predfile)
            assert set(d.split)=={'test'} and d.sample_id.nunique()==len(d)
            mm=m[m.split.eq('test')].set_index('sample_id').loc[d.sample_id]
            assert list(mm.mapped_label)==list(d.true_aami_label) and list(mm.subject_id)==list(d.subject_id)
            value=metrics(d,classes)
            exact_metric_match(value,load(f'{result}/test_metrics_{model}.json'))
            value['verified_against_saved_json']=True;value['prediction_source']=predfile
            value['error_directions']=[{'true':classes[i],'predicted':classes[j],'count':n} for i,row in enumerate(value['confusion_matrix']) for j,n in enumerate(row) if i!=j and n]
            evidence['test_metrics'][task][model]=value
            if model=='cnn_1d':
                wrong=d[~d.true_aami_label.eq(d.predicted_aami_label)]
                sample=wrong.groupby(['true_aami_label','predicted_aami_label'],sort=True).head(2)
                evidence['error_examples'][task]=records(sample)
        evidence['cnn_training'][task]=[x for x in load(f'results/classification/{task}44_v1/training_logs.json') if x['model']=='cnn_1d'][0]
    # NV and NSVF share identical patient assignments and exactly the same N/V windows.
    nv=metadata['nv']; nsvf=metadata['nsvf']
    sub=nsvf[nsvf.mapped_label.isin(['N','V'])]
    assert set(nv.sample_id)==set(sub.sample_id)
    assert dict(zip(nv.sample_id,nv.split))==dict(zip(sub.sample_id,sub.split))
    evidence['same_nv_windows_and_subject_split_across_tasks']=True
    # Class-weight strategies: validate every saved validation prediction against summary.
    dia='results/classification/nsvf44_v1/diagnosis'
    wp=frame(f'{dia}/weight_strategy_validation_predictions.csv')
    wt=frame(f'{dia}/weight_strategy_train_val_metrics.csv')
    evidence['weight_ablation']={}
    for strategy,g in wp.groupby('strategy',sort=False):
        v=metrics(g,['N','S','V','F'],'true_class','predicted_class')
        sr=wt[wt.strategy.eq(strategy)&wt.split.eq('val')].iloc[0]
        assert abs(v['accuracy']-sr.accuracy)<1e-12 and abs(v['macro_f1']-sr.macro_f1_present_classes)<1e-12
        assert set(g.sample_id)==set(nsvf[nsvf.split.eq('val')].sample_id)
        v['scope']='validation only, used for early stopping; exploratory comparison'
        evidence['weight_ablation'][strategy]=v
    evidence['weight_vectors']=records(frame(f'{dia}/weight_strategy_vectors.csv'))
    evidence['weight_train_metrics_saved_only']=records(wt[wt.split.eq('train')])
    evidence['existing_model_weight_reference']=records(frame(f'{dia}/existing_weighted_unweighted_validation_reference.csv'))
    # CV: independently recompute all 15 outer-fold metrics and pooled values.
    cv=f'{dia}/group_cv_5fold'
    log=load(f'{cv}/group_cv_training_log.json')
    fm=frame(f'{cv}/group_cv_fold_metrics.csv')
    summary=frame(f'{cv}/group_cv_summary.csv')
    trainval=nsvf[~nsvf.split.eq('test')]
    testsubjects=set(nsvf[nsvf.split.eq('test')].subject_id)
    assert log['subjects']==trainval.subject_id.nunique()==37 and log['samples']==len(trainval)==86286
    for f in log['folds']:
        tr=set(f['train_subjects']);va=set(f['validation_subjects'])
        assert not tr&va and not (tr|va)&testsubjects
        assert not set(f['inner_train_subjects'])&set(f['inner_validation_subjects'])
        assert (set(f['inner_train_subjects'])|set(f['inner_validation_subjects']))==tr
    cvo={}
    for model in MODELS:
        p=frame(f'{cv}/group_cv_oof_predictions_{model}.csv')
        assert len(p)==len(trainval) and p.sample_id.nunique()==len(p) and set(p.sample_id)==set(trainval.sample_id)
        assert set(p.subject_id).isdisjoint(testsubjects)
        vals=[];folds=[]
        for number,g in p.groupby('fold'):
            v=metrics(g,['N','S','V','F'],'true_class','predicted_class')
            saved=fm[fm.model.eq(model)&fm.fold.eq(number)].iloc[0]
            assert abs(v['macro_f1']-saved.macro_f1_present_classes)<1e-12 and abs(v['accuracy']-saved.accuracy)<1e-12
            assert json.loads(saved.confusion_matrix)==v['confusion_matrix']
            vals.append(v['macro_f1']);folds.append({'fold':int(number),**v})
        saved=summary[summary.model.eq(model)].iloc[0]
        assert abs(np.mean(vals)-saved.macro_f1_mean)<1e-12 and abs(np.std(vals,ddof=1)-saved.macro_f1_std)<1e-12
        cvo[model]={'macro_f1_mean':float(np.mean(vals)),'macro_f1_sample_std':float(np.std(vals,ddof=1)),
                    'folds':folds,'pooled_oof':metrics(p,['N','S','V','F'],'true_class','predicted_class')}
    evidence['group_cv']={'scope':log['scope'],'subjects':37,'samples':86286,'seed':log['seed'],'std_ddof':1,
                          'formal_test_subject_overlap':0,'predictions_all_covered_once':True,'models':cvo,
                          'fold_log':log,'saved_summary':records(summary)}
    evidence['model_config']=load('results/classification/nsvf44_v1/config.json')
    evidence['dataset_environment_recorded']=load('data/processed/mitdb44_nsvf_v1/environment.json')
    # Layer output sizes are computed analytically from actual padded Conv1d definitions.
    evidence['cnn_architecture']=[
        {'layer':'Input','shape':'B × 1 × 253','parameters':0},
        {'layer':'Conv1d 1→16 k7 p3 + ReLU','shape':'B × 16 × 253','parameters':128},
        {'layer':'MaxPool1d k2 stride2','shape':'B × 16 × 126','parameters':0},
        {'layer':'Conv1d 16→32 k5 p2 + ReLU','shape':'B × 32 × 126','parameters':2592},
        {'layer':'MaxPool1d k2 stride2','shape':'B × 32 × 63','parameters':0},
        {'layer':'Conv1d 32→64 k3 p1 + ReLU','shape':'B × 64 × 63','parameters':6208},
        {'layer':'AdaptiveAvgPool1d 1 + squeeze','shape':'B × 64','parameters':0},
        {'layer':'Linear 64→K','shape':'B × K','parameters_formula':'65K'}]
    evidence['cnn_parameter_counts']={'nv':9058,'nsvf':9188}
    evidence['limitations']=[
        'Fixed test already exposed historically; present audit is retrospective and does not restore independence.',
        'Cross-validation uses previously explored train+validation and fixed choices, so it is exploratory rather than external validation.',
        'N includes L/R/e/j and does not mean clinical health; NV excludes S/F/Q from task.',
        'Test F 370/371 beats are from subject_208; test S has only 10 beats and 3 subjects.',
        'N/V CNN validation Macro-F1 is 0.6630 versus test 0.9865, evidencing substantial split-dependent behavior.',
        'Filter is offline noncausal continuous-segment sosfiltfilt with five-second edge guards; not a causal online algorithm.',
        'Models require expert annotation centers, and contain no explicit RR interval or rhythm-context input.',
        'Legacy src/preprocessing/pipeline.py is an older 48-record pipeline; final 44-record artifact is src/datasets/build.py.',
        'Recorded environment JSON and lockfile describe historical runs; current bundled audit environment differs and is not the training environment.'
    ]
    for p in ['src/datasets/build.py','src/preprocessing/filters.py','src/preprocessing/extraction.py',
              'src/preprocessing/splitting.py','src/preprocessing/normalization.py','src/models/classifiers.py',
              'src/training/trainer.py','src/evaluation/four_class_diagnosis.py','src/labels.py',
              'requirements-lock.txt','results/classification/nsvf44_v1/diagnosis/final_error_case_samples_descriptive_only.csv']:
        source(p)
    evidence['source_inventory']=SOURCES
    (OUT/'verified_metrics.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
    write_report(evidence)
    return evidence

def write_report(e):
    lines=['# ECG-AI 实验素材审计','',f"核验时间：{e['verified_at_Asia_Shanghai']}",'',
           '本次仅读取现有工件、重算指标并核对源码；没有重新训练、改变模型、修改原始数据或重新选择方案。', '',
           '## 核验方法与证据等级','',
           '1. 数据数量从两个数据集的 `metadata.csv` 中筛选 included=True 后重新分组统计；逐一核对六个 NPZ 的行顺序、样本 ID、标签、患者 ID、形状和归一化。',
           '2. 正式测试指标从六个逐模型 `test_predictions_*.csv` 重新计算 Accuracy、各类 Precision/Recall/F1、Macro-F1 和混淆矩阵，均与保存的 JSON 一致（数值容差 1e-12）。',
           '3. 四种 CNN 权重验证指标从 `weight_strategy_validation_predictions.csv` 重算；五折的15组指标及 pooled OOF 从三个 OOF CSV 重算；检查每位患者组外层无交叉、每个样本恰好一次 OOF、正式测试患者不进入 CV。',
           '4. 历史训练设置和早停来自 config.json、training_logs.json 与源码。已有传统模型权重对照及权重实验训练集指标仅核对保存表，不声称此次从预测逐条重算。',
           '5. 原始 WFDB 标注逐条读取与哈希核对沿用项目已有 preprocessing_audit.json/verification.json；此次另外重新检查 metadata 与 NPZ 对齐，不把历史审计描述为本次全流程重跑。','',
           '逐文件哈希及所有数据表保存在 `paper/evidence/verified_metrics.json` 的 source_inventory 与各节。','',
           '## 数据与标签','',
           '正式数据入口为 `src/datasets/build.py`；`src/preprocessing/pipeline.py` 是早期48记录流程，不应用其配置代替正式44记录实验。官方48条记录中排除102、104、107、217。44记录对应43个受试者组，201与202共用subject_201_202。组ID由记录推导；这是已知重复患者的显式合并，并非另外取得的身份识别结果。','',
           'AAMI映射：N={N,L,R,e,j}；S={A,a,J,S}；V={V,E}；F={F}；Q={/,f,Q}。Q与非心拍、未映射符号不进入当前二/四分类。N不能解释为绝对健康，N/V分类不覆盖S、F、Q及所有心脏病。','']
    for task in ('nv','nsvf'):
        ds=e['datasets'][task]
        lines += [f"### {task.upper()} 实际样本划分",'', '| 划分 | 心拍数 | 受试者 | 记录 | '+' | '.join(ds['classes'])+' |',
                  '|---|---:|---:|---:|'+ '|'.join(['---:']*len(ds['classes']))+'|']
        for r in ds['splits']:
            lines.append('| '+' | '.join([r['split'],str(r['sample_count']),str(r['subject_count']),str(r['record_count'])]+[str(r[c]) for c in ds['classes']])+' |')
        lines.append('')
    lines += ['两任务共享完全相同患者划分与N/V样本ID。训练/验证/测试受试者31/6/6，无交叉；100和200因已探索固定为训练记录。分配协议为单次固定seed 20261027、约70%/15%/15%，按V注释数≥100分层，并预设留出V数量，不做性能驱动的反复分割。','',
              '### 四分类总体及患者覆盖','','| 类别 | 有效心拍 | 占比% | 有该类的受试者 | 最大患者 | 该患者份额% |','|---|---:|---:|---:|---|---:|']
    for r in e['datasets']['nsvf']['overall_class_counts']:
        lines.append(f"| {r['class']} | {r['samples']} | {r['share_pct']:.4f} | {r['subjects']} | {r['top_subject']} | {r['top_subject_share_pct']:.4f} |")
    lines += ['','| 划分 | 类别 | 心拍 | 有该类的受试者/划分总数 | 记录 | 最大患者 | 其份额% |','|---|---|---:|---:|---:|---|---:|']
    for r in e['datasets']['nsvf']['class_subject_coverage']:
        lines.append(f"| {r['split']} | {r['class']} | {r['sample_count']} | {r['subjects_with_class']}/{r['subjects_total']} | {r['records_with_class']} | {r['top_subject']} | {r['top_subject_share_pct']:.4f} |")
    lines += ['','`split_class_counts.csv`中各类subject_count/record_count已与metadata独立重算一致，使用的是修正后的类别覆盖数，不能用split总记录数替代。','',
              '## 预处理与模型结构','',
              '实际全部有效样本使用MLII导联、360Hz、mV。先对连续有限信号段以0.5–40Hz Butterworth SOS作sosfiltfilt离线双向滤波；原型阶数4，对应单次带通8阶，双向幅频响应为单次响应绝对值的平方。每段两端保留5秒保护区，因此不能称为因果实时滤波。','',
              '以专家注释位置r为中心截取[r−108,r+145)共253点，包含−0.3秒与+0.4秒端点，中心索引108。窗口越界、滤波边界/间断保护区、非有限、平坦、重复目标位置等技术失败会排除；大振幅或形态质量标记本身不等同于排除。','',
              '归一化为单一标量z-score：(x_filtered−μ_train)/σ_train，均值/标准差仅由有效训练心拍的全部采样点估计，ddof=0，不进行逐拍重缩放或截断。LR在253维向量上另用仅训练集拟合的逐维StandardScaler；RF直接用已做标量标准化的253维向量。','',
              '| 任务 | μ_train mV | σ_train mV | 训练心拍 |','|---|---:|---:|---:|']
    for t in ('nv','nsvf'):
        n=e['datasets'][t]['normalization']
        lines.append(f"| {t.upper()} | {n['mean_mV']:.12f} | {n['std_mV']:.12f} | {n['fit_beat_count']} |")
    lines += ['','| CNN层 | 输出 | 参数量 |','|---|---|---:|']
    for r in e['cnn_architecture']:
        lines.append(f"| {r['layer']} | {r['shape']} | {r.get('parameters',r.get('parameters_formula'))} |")
    lines += ['','B为批量、K为类别数；总参数N/V为9058，四分类9188。无BatchNorm、Dropout、LSTM或显式RR间期分支。softmax用于推理概率，训练接收logits。','',
              'LR：C=1、balanced、lbfgs、max_iter=1000、tol=0.001。RF：100棵树、max_depth=18、min_samples_leaf=2、max_features=sqrt、balanced_subsample、bootstrap=True、max_samples=0.8、n_jobs=−1。三模型seed=20261027。CNN使用Adam、学习率0.001、weight_decay=1e−5、batch=256、最多25轮、patience=5、加权交叉熵；权重n/(K n_c)仅由训练集计算，按验证Macro-F1保存最佳检查点。','',
              '| 任务 | 实际轮次 | 最佳轮次 | 最佳验证Macro-F1 | CPU/权重向量 |','|---|---:|---:|---:|---|']
    for t,r in e['cnn_training'].items():
        lines.append(f"| {t.upper()} | {r['epochs_ran']} | {r['best_epoch']} | {r['best_val_macro_f1']:.6f} | {r['device']} / {r['training_class_weights']} |")
    lines += ['','## 正式测试指标 独立重算','','以下均为test_predictions文件，不是验证集指标；只沿用历史测试，不重新调参。','']
    for t,d in e['test_metrics'].items():
        lines += [f'### {t.upper()}', '', '| 模型 | Accuracy | Macro-F1 | 类别 | Precision | Recall | F1 | 支持数 |','|---|---:|---:|---|---:|---:|---:|---:|']
        for model,v in d.items():
            for c,r in v['per_class'].items():
                lines.append(f"| {model} | {v['accuracy']:.6f} | {v['macro_f1']:.6f} | {c} | {r['precision']:.6f} | {r['recall']:.6f} | {r['f1']:.6f} | {r['support']} |")
        lines.append('')
    lines += ['N/V CNN混淆矩阵（行真值N,V；列预测N,V）=[[12240,47],[11,1150]]，共58错。四分类CNN主要错误N→S=2626、F→N=216、F→V=154。四分类RF虽然Accuracy更高，但S与F召回均为0；CNN的S召回为0，F仅1/371。不能据总体准确率推导各类别均有效。','',
              'N/V CNN验证Macro-F1仅0.663009而正式测试为0.986520，应说明固定划分患者组成明显影响结果；高测试分数不能单独证明患者间稳定性。', '',
              '## 类别权重消融','',
              '四种CNN权重策略都在既有train训练、validation比较，检查点同样使用validation早停，因此这是探索性调参与诊断证据。平方根策略是sqrt(n/(K n_c))后除以权重均值；截断策略先min(n/(K n_c),10)再除以均值；全逆频率策略不作均值归一化。不能声称截断前已mean-one。','',
              '| 策略 | 验证Accuracy | 验证Macro-F1 | N召回 | S精确率/召回 | F精确率/召回 | 预测S/F占比% |','|---|---:|---:|---:|---:|---:|---:|']
    for s,v in e['weight_ablation'].items():
        p=v['per_class']
        lines.append(f"| {s} | {v['accuracy']:.6f} | {v['macro_f1']:.6f} | {p['N']['recall']:.6f} | {p['S']['precision']:.6f}/{p['S']['recall']:.6f} | {p['F']['precision']:.6f}/{p['F']['recall']:.6f} | {p['S']['predicted_share_pct']:.4f}/{p['F']['predicted_share_pct']:.4f} |")
    lines += ['','传统模型既有加权/无权重验证表见JSON的existing_model_weight_reference。其效应不同：LR Macro-F1从加权0.2637到无权重0.3371；RF从0.4019到0.4090；CNN从加权0.4735到无权重0.3914。均只描述此划分与配置，不能断言任何权重普遍有效或普遍有害。', '',
              '## 五折受试者分组交叉验证','',
              '只用原train+validation的86286拍、37患者组，StratifiedGroupKFold五折、shuffle=True、seed=20261028。每个外折中患者无交叉；CNN以外层训练患者的四折分组方案选一个有效内层早停划分，再按该内层最佳epoch在完整外层训练集重拟合。标量归一化与类别权重都只由相应训练组拟合；正式test六患者完全未进入CV。','',
              '| 模型 | 外折Macro-F1均值 | 样本标准差 ddof=1 | pooled OOF Macro-F1 | 各折Macro-F1 |','|---|---:|---:|---:|---|']
    for m,v in e['group_cv']['models'].items():
        folds=', '.join(f"{f['macro_f1']:.4f}" for f in v['folds'])
        lines.append(f"| {m} | {v['macro_f1_mean']:.6f} | {v['macro_f1_sample_std']:.6f} | {v['pooled_oof']['macro_f1']:.6f} | {folds} |")
    lines += ['','各折F支持为5、17、5、37、365，极不均匀。各折所有四类均有真实支持，所以本次macro_f1_present_classes与固定四类Macro-F1相同；不应推广到缺类患者指标。配置此前已依据原验证行为确定，故CV虽无患者重叠，仍是探索性稳定性诊断，不是完全未触碰的独立或外部验证。','',
              '## 真实错误案例','',
              '可直接引用的四分类最终选择表：`results/classification/nsvf44_v1/diagnosis/final_error_case_samples_descriptive_only.csv`。212:1427（record212，329145，原符号R）N→S；208:1482（313756，F）F→N；208:1293（271553，F）F→V；116:1799（488586，V）V→N。均为既有测试回顾，用于定性展示，不作为选模依据。','',
              '诊断六面板图源 `figures/11_four_class_diagnosis/cnn_test_error_waveforms_descriptive_only.png` 对应的案例表为 `cnn_test_error_waveform_cases_descriptive_only.csv`；勿把不同选择表中的ID误配给该图。最终重绘样本另见 figures/12_final_report 下的索引（由主写作流程核对）。N/V错误候选及原始预测概率已保存在JSON的error_examples.nv。','',
              '## 环境与可复现边界','',
              '数据构建environment.json记录Python 3.12.10、NumPy 2.5.4、Pandas 3.1.0、WFDB 4.3.1、SciPy 1.18.1、Scikit-learn 1.9.1；requirements-lock.txt固定torch 2.14.1。训练日志明确device=cpu。锁文件描述可复现依赖，不是训练当时逐包运行时探针；操作系统和CPU具体型号若无额外日志，不应凭空填写。当前捆绑审计解释器版本与历史训练依赖不同。','',
              '复查命令：使用捆绑Python运行 `paper/tools/audit_experiments.py`。脚本只读取原有数据/结果，更新paper/evidence下两个核验文件，不训练。','',
              '## 应写入论文的限制','']
    lines.extend('- '+s for s in e['limitations'])
    lines += ['','## 核验结论','',
              '六个正式测试预测文件、四策略验证预测、十五个外折指标均重算匹配；元数据与NPZ对齐、患者互斥、201/202合并及修正后的类别患者/记录覆盖均通过。不能由此推断模型有临床有效性，也不能把已暴露测试再次命名为全新盲测。']
    (OUT/'experiment_audit.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')

if __name__=='__main__':
    e=audit()
    print(json.dumps({'passed':True,'datasets':{t:v['splits'] for t,v in e['datasets'].items()},
                     'test':{t:{m: {'accuracy':v['accuracy'],'macro_f1':v['macro_f1']} for m,v in d.items()} for t,d in e['test_metrics'].items()},
                     'cv':{m:{k:v[k] for k in ('macro_f1_mean','macro_f1_sample_std')} for m,v in e['group_cv']['models'].items()}},ensure_ascii=False,indent=2))
