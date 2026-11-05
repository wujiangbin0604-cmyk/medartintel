"""Independent audits of previous statistics and completed NPZ datasets."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import wfdb
from ..download import sha256
from ..labels import AAMI_MAP
from .normalization import transform,fit_train_standardizer
from .splitting import SPLITS


def audit_previous_statistics(root):
    rows=[]
    for directory in (root/'results',root/'results/visualization'):
        config_path=directory/'run_config.json'
        if not config_path.exists(): continue
        config=json.loads(config_path.read_text(encoding='utf-8')); records=config['records']
        symbols=Counter(s for name in records for s in wfdb.rdann(str(root/'data/mitdb'/name),'atr').symbol)
        raw=pd.read_csv(directory/'raw_symbol_counts.csv',keep_default_na=False)
        good=symbols==dict(zip(raw.symbol,raw['count'].astype(int)))
        classes=Counter()
        for symbol,count in symbols.items():
            if symbol in AAMI_MAP: classes[AAMI_MAP[symbol]]+=count
        actual=pd.read_csv(directory/'aami_counts.csv',keep_default_na=False)
        mapped_good=all(classes.get(row.aami_group,0)==int(row.count) for row in actual.itertuples())
        rows.append({'source':str(directory.relative_to(root)),'records':','.join(records),
                     'total_annotations':sum(symbols.values()),'raw_symbol_counts_match':good,'aami_counts_match':mapped_good})
        if not good or not mapped_good: raise AssertionError(f'Previous label statistics mismatch: {directory}')
    return pd.DataFrame(rows)


def verify_dataset(directory,metadata,manifest,normalization,raw_directory,expected_length=253,min_v=200):
    included=metadata[metadata.included].copy(); all_ids=set(); subject_sets={}; totals={}
    filtered_train=None; train_ids=None
    for split in SPLITS:
        part=included[included.split==split].sort_values('npz_row')
        with np.load(directory/f'{split}.npz',allow_pickle=False) as data:
            x,y,raw=data['X'],data['y'],data['X_filtered']
            if x.shape!=(len(part),1,expected_length) or raw.shape!=x.shape: raise AssertionError('NPZ shape mismatch')
            if x.dtype!=np.float32 or not np.isfinite(x).all() or not np.isfinite(raw).all(): raise AssertionError('Invalid NPZ values')
            if not np.array_equal(y,part.target_label.to_numpy()): raise AssertionError('Labels mismatch metadata')
            for key in ('sample_id','record_id','subject_id','original_label','mapped_label','lead'):
                if not np.array_equal(data[key],part[key].astype(str).to_numpy()): raise AssertionError(f'{key} mismatch')
            if not np.array_equal(data['annotation_sample'],part.annotation_sample.to_numpy()): raise AssertionError('Original annotation mismatch')
            if not np.allclose(x,transform(raw,normalization),atol=1e-6,rtol=1e-6): raise AssertionError('Normalization mismatch')
            ids=set(data['sample_id'].tolist())
            if len(ids)!=len(part) or all_ids.intersection(ids): raise AssertionError('Sample duplicate across sets')
            all_ids.update(ids); subject_sets[split]=set(data['subject_id'].tolist())
            totals[split]={'samples':len(part),'N':int((part.mapped_label=='N').sum()),'V':int((part.mapped_label=='V').sum()),
                           'subjects_with_samples':len(subject_sets[split]),'records_with_samples':part.record_id.nunique()}
            if totals[split]['V']<min_v: raise AssertionError('Predeclared minimum V count is not met; do not adapt test split')
            if split=='train':
                filtered_train=raw.copy(); train_ids=data['sample_id'].tolist()
                if not np.isclose(x.mean(dtype=np.float64),0,atol=2e-6) or not np.isclose(x.std(dtype=np.float64),1,atol=2e-6):
                    raise AssertionError('Training normalization not zero mean/unit std')
    for a,b in (('train','val'),('train','test'),('val','test')):
        if subject_sets[a].intersection(subject_sets[b]): raise AssertionError('Subject leakage')
    mapping=metadata.groupby('record_id').split.first()
    if mapping['201']!=mapping['202']: raise AssertionError('201/202 leakage')
    if mapping['100']!='train' or mapping['200']!='train': raise AssertionError('Previously explored records leaked into holdout')
    fitted=fit_train_standardizer(filtered_train,train_ids)
    for key in ('mean_mV','std_mV','fit_beat_count','fit_value_count','training_sample_ids_sha256'):
        if fitted[key]!=normalization[key]: raise AssertionError('Normalizer was not fitted on the exact train export')
    for row in manifest:
        if row['file'].endswith(('.dat','.hea','.atr')) and sha256(raw_directory/row['file'])!=row['sha256']:
            raise AssertionError('Raw data changed')
    return {'passed':True,'dataset_ready':True,'full_record_count':metadata.record_id.nunique(),
            'subject_count':metadata.subject_id.nunique(),'split_counts':totals,'window_length':expected_length,
            'shape_convention':'N,1,time','all_values_finite':True,'normalizer_fitted_only_on_train':True,
            'subject_overlap':0,'record_201_202_same_split':True,'prior_eda_records_100_200_train_only':True,
            'original_annotation_ids_preserved':True,'original_files_unchanged':True,
            'sampling':'none; all eligible beats retained, no oversampling/undersampling',
            'classifier_trained':False,'test_used_for_model_or_filter_selection':False}
