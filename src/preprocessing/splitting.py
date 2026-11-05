"""A single prespecified subject split, locked before any filter comparison."""
import hashlib
import json
import numpy as np
import pandas as pd
import wfdb
from ..labels import AAMI_MAP

SUBJECT_SOURCE='https://physionet.org/files/mitdb/1.0.0/mitdbdir/intro.htm'
SPLITS=('train','val','test')


def subject_id(record_id):
    return 'subject_201_202' if str(record_id) in ('201','202') else f'subject_{record_id}'


def annotation_census(directory,records):
    rows=[]
    for name in records:
        ann=wfdb.rdann(str(directory/name),'atr')
        groups=[AAMI_MAP.get(s,'') for s in ann.symbol]
        rows.append({'record_id':name,'subject_id':subject_id(name),'annotation_count':len(ann.sample),
                     **{f'{g}_annotation_count':groups.count(g) for g in ('N','S','V','F','Q')}})
    return pd.DataFrame(rows)


def lock_subject_split(census,path,manifest,seed=20261027):
    counts=census.groupby('subject_id')[[f'{g}_annotation_count' for g in ('N','S','V','F','Q')]].sum()
    records=sorted(census.record_id.tolist())
    raw_hashes={row['file']:row['sha256'] for row in manifest if row['file'].endswith(('.dat','.hea','.atr'))}
    protocol={'seed':seed,'ratios':[.70,.15,.15],'rich_v_threshold':100,'minimum_v_per_holdout':200,
              'forced_train_records':['100','200'],'algorithm':'single seeded rich-V subject stratification; no search or retries'}
    if path.exists():
        plan=json.loads(path.read_text(encoding='utf-8'))
        if plan['raw_sha256']!=raw_hashes or plan['protocol']!=protocol or plan['records']!=records:
            raise ValueError('Existing split plan differs; use a new versioned output directory, never silently reshuffle')
        mapping=plan['subject_to_split']
        if set(mapping)!=set(counts.index): raise ValueError('Locked split does not cover all subjects')
    else:
        forced={subject_id(r) for r in ('100','200') if r in records}
        names=sorted(counts.index); n=len(names)
        n_val=round(n*.15); n_test=round(n*.15)
        if n_val<2 or n_test<2: raise ValueError('Formal construction needs the full database, not two exploratory records')
        rich=[s for s in names if counts.loc[s,'V_annotation_count']>=100 and s not in forced]
        other=[s for s in names if counts.loc[s,'V_annotation_count']<100 and s not in forced]
        total_rich=int((counts.V_annotation_count>=100).sum())
        val_rich=max(2,round(total_rich*.15)); test_rich=max(2,round(total_rich*.15))
        if val_rich+test_rich>len(rich) or max(val_rich,test_rich)>min(n_val,n_test):
            raise ValueError('Insufficient independent V-rich subjects for the prespecified split')
        rng=np.random.default_rng(seed)
        rich=list(rng.permutation(rich)); other=list(rng.permutation(other))
        val=rich[:val_rich]+other[:n_val-val_rich]
        test=rich[val_rich:val_rich+test_rich]+other[n_val-val_rich:n_val-val_rich+n_test-test_rich]
        if len(val)!=n_val or len(test)!=n_test: raise ValueError('Insufficient non-rich subjects for stratification')
        mapping={s:'val' if s in val else 'test' if s in test else 'train' for s in names}
        for split in SPLITS:
            selected=[s for s in names if mapping[s]==split]
            if counts.loc[selected,'V_annotation_count'].sum()<200:
                raise ValueError('Predeclared minimum V count failed; no automatic split retries')
        plan={'protocol':protocol,'records':records,'raw_sha256':raw_hashes,'subject_to_split':mapping,
              'subject_id_rule':'record-based pseudonymous group IDs; only 201 and 202 share a group',
              'subject_id_source':SUBJECT_SOURCE,
              'rationale':'100/200 were already explored and are reserved for training. Before waveform processing, expert-label counts define a V>=100 stratum. Each holdout reserves at least two such independent subjects. No test waveform, normalization, classifier, or performance score is used.',
              'adjustments':'No iterative adjustment or split search; V-presence constraints are specified before the one seeded allocation.'}
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8') as stream: json.dump(plan,stream,ensure_ascii=False,indent=2)
    result=census.copy(); result['split']=result.subject_id.map(mapping)
    if result.groupby('subject_id').split.nunique().max()!=1: raise AssertionError('Subject leakage')
    if not set(result.split)==set(SPLITS): raise AssertionError('Missing dataset split')
    if '201' in records and '202' in records and mapping[subject_id('201')]!=mapping[subject_id('202')]:
        raise AssertionError('201/202 leakage')
    return result,plan
