"""Build the complete, subject-independent training data artifact without training."""
import argparse
from dataclasses import asdict
from datetime import datetime
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from ..download import prepare_data,sha256
from ..io import load_record
from ..analysis import primary_channel,summarize_labels
from ..labels import AAMI_MAP,GROUPS
from .audit import audit_previous_statistics,verify_dataset
from .filters import FilterConfig,filter_continuous,morphology_metrics
from .splitting import annotation_census,lock_subject_split,SPLITS
from .extraction import extract_record
from .normalization import fit_train_standardizer,transform


def json_file(value,path):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def run(root,output,offline=False,seed=20261027,groups=('N','V'),split_path=None):
    from .plots import generate_figures
    from .report import generate_report
    result=root/'results/preprocessing'; result.mkdir(parents=True,exist_ok=True)
    output.mkdir(parents=True,exist_ok=True)
    json_file({'passed':False,'dataset_ready':False,'status':'running_or_incomplete'},output/'verification.json')
    prior=audit_previous_statistics(root); prior.to_csv(result/'prior_statistics_audit.csv',index=False,encoding='utf-8-sig')
    names,manifest=prepare_data(root/'data/mitdb',['all'],offline,workers=4,mirror='s3')
    if len(names)!=48: raise ValueError('Formal MIT-BIH build requires the official 48-record list')
    census=annotation_census(root/'data/mitdb',names)
    split_path=split_path or output/'split_plan.json'
    split_manifest,plan=lock_subject_split(census,split_path,manifest,seed)
    split_manifest.to_csv(output/'split_manifest.csv',index=False,encoding='utf-8-sig')
    print('Subject split LOCKED before signal/filter analysis',flush=True)
    selected_filter=FilterConfig()
    candidate_filters=[selected_filter,FilterConfig(.5,45.),FilterConfig(1.,40.)]
    protocol={'version':'nv_v1','created_at_Asia_Shanghai':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
              'records':names,'seed':seed,'classes':list(groups),'target_label_map':{g:i for i,g in enumerate(groups)},
              'full_aami_mapping':AAMI_MAP,'pre_s':.3,'post_s':.4,'fs_hz':360.,'window_length':253,'center_index':108,
              'endpoint_convention':'[annotation_sample-108, annotation_sample+145); both -0.3s/+0.4s samples included',
              'lead_policy':'MLII by name; if absent use actual first lead; preserve lead/channel per sample',
              'filter':selected_filter.parameters(360.),'candidate_filters_training_only':[f.parameters(360.) for f in candidate_filters],
              'filter_selection':'0.5-40 Hz fixed a priori; alternatives are training-only descriptive audits, no optimization',
              'normalization':'global scalar mean/std fitted on accepted float32 training filtered windows only',
              'sampling':'none; all technically eligible target beats retained in every split',
              'technical_exclusions':['not_target_group','non_beat_annotation','unknown_or_unmapped_annotation','window_boundary',
                                      'duplicate_target_beat_position','nonfinite_raw_window','invalid_filtered_window',
                                      'filter_edge_or_gap_guard','flat_raw_window','flat_filtered_window'],
              'quality_flags_are_not_exclusions':{'raw_abs_amplitude_mV':5,'raw_peak_to_peak_mV':8,'correlation_below':.90,
                                                 'amplitude_ratio_outside':[.5,1.5],'peak_shift_abs_ms_above':10,'normalized_abs_z_above':20},
              'split_plan_path':str(split_path.resolve()),'split_plan_sha256':sha256(split_path),
              'test_policy':'No test signal used for filter setting, sampling choice, normalization fitting or model tuning',
              'classifier_trained':False,'root':str(root),'output_directory':str(output)}
    # Persist the method before processing any waveform, so it cannot depend on held-out observations.
    json_file(protocol,output/'processing_config.json')
    all_metadata=[]; all_original_annotations=[]; vectors=[]; record_checks=[]; training_filter_metrics=[]; contexts={}
    global_row=0
    for record_id in names:
        print(f'Preprocess/extract {record_id}',flush=True)
        record,checks=load_record(root/'data/mitdb',record_id)
        if record.fs!=360.: raise ValueError('Unexpected MIT-BIH sampling rate; do not silently resample')
        entry=split_manifest[split_manifest.record_id==record_id].iloc[0]
        metadata,values,raw,filtered,accepted=extract_record(record,entry.split,entry.subject_id,selected_filter,groups)
        metadata['global_row']=-1
        metadata.loc[accepted,'global_row']=np.arange(global_row,global_row+len(values)); global_row+=len(values)
        all_metadata.append(metadata); vectors.append(values); all_original_annotations.append(record.annotations)
        channel=primary_channel(record)
        record_checks.append({**checks,'record_id':record_id,'subject_id':entry.subject_id,'split':entry.split,
                              'selected_lead':record.leads[channel],'selected_channel':channel,'included_samples':len(values)})
        if entry.split=='train' and len(values):
            for candidate in candidate_filters:
                candidate_signal=filtered if candidate==selected_filter else filter_continuous(record.signal[:,channel],record.fs,candidate)[0]
                candidate_windows=np.stack([candidate_signal[int(metadata.loc[i,'window_start_sample']):int(metadata.loc[i,'window_stop_sample_exclusive'])] for i in accepted])
                metrics=morphology_metrics(raw,candidate_windows,record.fs,108)
                frame=pd.DataFrame(metrics); frame['mapped_label']=metadata.loc[accepted,'mapped_label'].to_numpy()
                for group,part in frame.groupby('mapped_label'):
                    training_filter_metrics.append({'record_id':record_id,'subject_id':entry.subject_id,'split':'train',
                        'lead':record.leads[channel],'mapped_label':group,'low_hz':candidate.low_hz,'high_hz':candidate.high_hz,'n':len(part),
                        'correlation_median':float(part.raw_filtered_correlation.median()),
                        'correlation_q05':float(part.raw_filtered_correlation.quantile(.05)),
                        'ptp_ratio_median':float(part.filtered_raw_ptp_ratio.median()),
                        'peak_shift_abs_ms_median':float(part.local_peak_shift_ms.abs().median()),
                        'corr_below_0_90_count':int((part.raw_filtered_correlation<.90).sum())})
        if record_id in ('100','200'):
            if entry.split!='train': raise AssertionError('Illustration records must remain training-only')
            contexts[record_id]={'record':record,'channel':channel,'filtered':filtered,
                                 'alternatives':{f'{c.low_hz:g}-{c.high_hz:g}Hz':filter_continuous(record.signal[:,channel],record.fs,c)[0] for c in candidate_filters}}
    metadata=pd.concat(all_metadata,ignore_index=True)
    filtered_values=np.concatenate(vectors,axis=0)
    accepted_meta=metadata[metadata.included].sort_values('global_row')
    if not np.array_equal(accepted_meta.global_row.to_numpy(),np.arange(len(filtered_values))): raise AssertionError('Global vector row alignment failed')
    train_meta=accepted_meta[accepted_meta.split=='train']
    normalizer=fit_train_standardizer(filtered_values[train_meta.global_row.to_numpy()],train_meta.sample_id.tolist())
    normalizer['training_subject_ids']=sorted(train_meta.subject_id.unique().tolist())
    normalizer['training_record_ids']=sorted(train_meta.record_id.unique().tolist())
    json_file(normalizer,output/'normalization.json')
    metadata['npz_row']=-1
    split_stats=[]
    for split in SPLITS:
        part=metadata[metadata.included & (metadata.split==split)].sort_values('global_row')
        indices=part.global_row.to_numpy(dtype=int)
        unscaled=filtered_values[indices,None,:]
        normalized=transform(unscaled,normalizer)
        metadata.loc[part.index,'npz_row']=np.arange(len(part))
        for row_index,large in zip(part.index,np.max(np.abs(normalized),axis=(1,2))>20):
            if large:
                old=metadata.loc[row_index,'quality_flags']
                metadata.loc[row_index,'quality_flags']=(old+';' if old else '')+'large_train_standardized_z'
        payload={'X':normalized,'X_filtered':unscaled,'y':part.target_label.to_numpy(dtype=np.int64),
                 'annotation_sample':part.annotation_sample.to_numpy(dtype=np.int64),'fs_hz':np.array(360.),
                 'class_names':np.array(groups),'center_index':np.array(108),'relative_time_s':np.arange(-108,145)/360}
        for name in ('sample_id','record_id','subject_id','original_label','mapped_label','lead'):
            payload[name]=part[name].astype(str).to_numpy(dtype=str)
        np.savez_compressed(output/f'{split}.npz',**payload)
        for group in groups:
            split_stats.append({'split':split,'mapped_label':group,'sample_count':int((part.mapped_label==group).sum()),
                                'subject_count_total':part.subject_id.nunique(),'record_count_total':part.record_id.nunique()})
    # CSV-safe auxiliary text plus lossless JSON-escaped original auxiliary annotation.
    metadata.drop(columns=['aux_note']).to_csv(output/'metadata.csv',index=False,encoding='utf-8-sig')
    annotations=pd.concat(all_original_annotations,ignore_index=True)
    tables=summarize_labels(annotations,names)
    tables.update({'record_checks':pd.DataFrame(record_checks),'split_class_counts':pd.DataFrame(split_stats),
                   'filter_comparison_training':pd.DataFrame(training_filter_metrics),'download_manifest':pd.DataFrame(manifest),
                   'exclusion_counts':metadata.groupby(['split','exclusion_reason']).size().reset_index(name='count'),
                   'subject_sample_counts':metadata[metadata.included].groupby(['subject_id','split','mapped_label']).size().reset_index(name='count')})
    for name,table in tables.items(): table.to_csv(result/f'{name}.csv',index=False,encoding='utf-8-sig')
    json_file({'python':platform.python_version(),**{m:version(m) for m in ('wfdb','numpy','pandas','matplotlib','scipy')}},output/'environment.json')
    training_counts=metadata[metadata.included & (metadata.split=='train')].mapped_label.value_counts()
    json_file({'source':'training samples only','inverse_frequency_balanced_weights':
               {g:float(training_counts.sum()/(len(groups)*training_counts[g])) for g in groups},
               'applied':False},output/'training_class_weights.json')
    figures=generate_figures(root,metadata,filtered_values,normalizer,contexts,tables,protocol)
    figures.to_csv(result/'figure_catalog.csv',index=False,encoding='utf-8-sig')
    verification=verify_dataset(output,metadata,manifest,normalizer,root/'data/mitdb')
    verification['split_plan_sha256']=sha256(split_path)
    verification['figure_count']=len(figures)
    verification['output_hashes']={f'{split}.npz':sha256(output/f'{split}.npz') for split in SPLITS}
    json_file(verification,output/'verification.json')
    generate_report(root,output,metadata,tables,protocol,normalizer,verification,figures,prior,plan)
    print(json.dumps(verification,ensure_ascii=False,indent=2),flush=True)
    return verification


def main():
    parser=argparse.ArgumentParser(description='Construct all-record, patient-independent ECG datasets, without model training')
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    parser.add_argument('--output-dir',type=Path,default=Path('data/processed/nv_v1'))
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--seed',type=int,default=20261027)
    parser.add_argument('--classes',nargs='+',choices=GROUPS,default=['N','V'])
    parser.add_argument('--split-plan',type=Path)
    args=parser.parse_args(); root=args.root.resolve()
    if len(set(args.classes))!=len(args.classes) or not {'N','V'}.issubset(args.classes): parser.error('Unique classes including N and V are required')
    output=args.output_dir if args.output_dir.is_absolute() else root/args.output_dir
    plan=(args.split_plan if args.split_plan.is_absolute() else root/args.split_plan) if args.split_plan else None
    run(root,output.resolve(),args.offline,args.seed,tuple(args.classes),plan)


if __name__=='__main__': main()
