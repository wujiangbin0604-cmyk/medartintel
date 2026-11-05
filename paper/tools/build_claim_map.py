"""Record manuscript claims against physical experiment artifacts."""
from pathlib import Path
import csv,json
P=Path(__file__).resolve().parents[1]; root=P.parent
j=json.loads((P/'evidence/verified_metrics.json').read_text(encoding='utf-8'))
rows=[]
def add(pos,claim,value,src,fig='',notes='',verified='是'):
    rows.append({'论文位置':pos,'结论文本':claim,'指标或数据':value,'来源文件':src,'表格或图像路径':fig,'是否核验':verified,'备注':notes})
for task,models in j['test_metrics'].items():
    section='5.1' if task=='nv' else '5.2'; table='表4 表5 图7' if task=='nv' else '表6 图6'
    for name,m in models.items():
        src=m['prediction_source']
        for key in ['accuracy','macro_f1']:
            add(section,f'{task} {name} 测试{key}',f'{m[key]:.12f}',src,table,'本次从逐拍预测重算并匹配保存JSON；历史测试已暴露')
        for cls,vals in m['per_class'].items():
            for key in ['precision','recall','f1','support']:
                add(section,f'{task} {name} {cls}类 {key}',str(vals[key]),src,table,'固定测试集，按心拍统计')
        add(section,f'{task} {name} 混淆矩阵',json.dumps(m['confusion_matrix']),src,table,'行真实，列预测；类序见任务配置')
for task,ds in j['datasets'].items():
    src=f'data/processed/mitdb44_{task}_v1/metadata.csv'
    for v in ds['splits']:
        add('2.4',f'{task} {v["split"]}有效拍数与患者记录数',json.dumps(v,ensure_ascii=False),src,'表2','included=True后独立聚合；201/202合并')
    for v in ds['overall_class_counts']:
        add('2.5 5.3',f'{task} {v["class"]}总体数量与患者覆盖',json.dumps(v,ensure_ascii=False),src,'图4 图8','患者集中度从逐拍元数据重算')
    for v in ds['class_subject_coverage']:
        add('5.3',f'{task} {v["split"]} {v["class"]}来源患者与集中度',json.dumps(v,ensure_ascii=False),src,'图8','修正后的类别级覆盖数')
extras=[
('2.1','44记录43患者 201/202合并','44/43','data/processed/mitdb44_nv_v1/split_manifest.csv','表2','另由PhysioNet官方数据页核验重复患者'),
('2.3','滤波与253点截窗','0.5—40Hz 原型4阶 单程带通8阶 sosfiltfilt 5秒保护区','data/processed/mitdb44_nv_v1/processing_config.json;src/datasets/build.py;src/preprocessing/filters.py','图2 图3','非因果离线处理'),
('2.3','N/V标量归一化参数','μ=0.010122829268587038 σ=0.3422525506986414','data/processed/mitdb44_nv_v1/normalization.json','公式2','仅训练侧拟合'),
('3.3','实际CNN结构与参数','253→126→63→1；9058/9188参数','src/models/classifiers.py','表3 图5','按实际定义推导与审计'),
('3.4','训练设置和最佳epoch','Adam lr0.001 batch256 max25 patience5；最佳12/11','results/classification/nv44_v1/config.json;results/classification/nv44_v1/training_logs.json;results/classification/nsvf44_v1/training_logs.json','','保存设置，不重训'),
('5.1','N/V验证与测试Macro-F1差异','0.663009 / 0.986520','results/classification/nv44_v1/training_logs.json;results/classification/nv44_v1/test_predictions_cnn_1d.csv','','划分依赖，不能高估稳定性'),
('5.4','CNN四权重验证对照','验证Accuracy Macro-F1和每类P/R/F1','results/classification/nsvf44_v1/diagnosis/weight_strategy_validation_predictions.csv;results/classification/nsvf44_v1/diagnosis/weight_strategy_class_metrics.csv','表7 图9','验证用于早停，属探索性；本次从验证预测重算'),
('5.4','LR RF既有权重对照','LR 0.2637/0.3371 RF 0.4019/0.4090','results/classification/nsvf44_v1/diagnosis/existing_weighted_unweighted_validation_reference.csv','','已有保存表核对；未重新训练'),
('5.5','五折范围与分组流程','train+val 86286拍37组；F折支持5/17/5/37/365','results/classification/nsvf44_v1/diagnosis/group_cv_5fold/group_cv_training_log.json;results/classification/nsvf44_v1/diagnosis/group_cv_5fold/group_cv_fold_metrics.csv','表8 图10','外层互斥；内层选择一个分组早停划分'),
('5.5','五折Macro-F1均值与样本标准差','LR0.304687±0.037711 RF0.417258±0.042395 CNN0.356418±0.062353','results/classification/nsvf44_v1/diagnosis/group_cv_5fold/group_cv_oof_predictions_logistic_regression.csv;results/classification/nsvf44_v1/diagnosis/group_cv_5fold/group_cv_oof_predictions_random_forest.csv;results/classification/nsvf44_v1/diagnosis/group_cv_5fold/group_cv_oof_predictions_cnn_1d.csv','表8 图10','本次按外折重算；ddof=1；不是标准误'),
('5.6','实际错误案例及采样时间','111:62 53.175s；208:32 18.822s；208:19 11.381s','results/classification/nsvf44_v1/diagnosis/cnn_test_error_waveform_cases_descriptive_only.csv;results/classification/nsvf44_v1/test_predictions_cnn_1d.csv','图11','sample_id后缀是完整标注流索引'),
('6.1 6.2','系统架构和真实模型路径','React Umi AntDesign ECharts / FastAPI / ECGStore ModelRegistry','web/frontend/package.json;web/frontend/.umirc.ts;web/backend/ecg_service.py;web/backend/model_registry.py;web/backend/app.py','图12—15','静态源码与历史运行证据交叉核验'),
('6.3','动画互动游戏与欢迎引导已实现','路由组件 API 历史测试记录','web/docs/games/heartbeat_hunter_testing.md;web/docs/welcome_onboarding.md;web/backend/heartbeat_hunter.py;web/frontend/.umirc.ts','','未验证教学效果'),
('6.4','部署类别一致与概率误差','600/600；max|Δp|=4.76837158203125e-07；输入差0','web/results/phase2_validation/validation_prediction_comparison.csv;web/results/phase2_validation/validation_sample_manifest.csv;web/results/phase2_validation/validation_summary.json','','本次直接复算与当前6工件哈希比对；不是分类正确率'),
('6.4','历史后端与浏览器测试记录','18 passed / 16 passed','web/docs/phase4_backend.log;web/docs/visual_fidelity/e2e_final.log','','历史记录本次未重新执行；不同阶段不可相加'),
]
for x in extras: add(*x)
with (P/'evidence/claim_evidence_map.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
missing=[]
for row in rows:
    for src in row['来源文件'].split(';'):
        if not (root/src).exists(): missing.append(src)
assert not missing,missing
print(f'{len(rows)} claims mapped; all local evidence paths exist.')
