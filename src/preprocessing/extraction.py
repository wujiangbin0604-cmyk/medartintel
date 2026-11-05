"""Metadata-first extraction: retain every annotation, reject only fixed technical failures."""
import numpy as np
import pandas as pd
from ..analysis import primary_channel
from .filters import filter_continuous,morphology_metrics


def extract_record(record,split,subject,config,groups=('N','V'),pre_s=.3,post_s=.4):
    fs=record.fs; pre=round(pre_s*fs); post=round(post_s*fs)
    channel=primary_channel(record); lead=record.leads[channel]
    if record.units[channel]!='mV': raise ValueError('Explicit mV calibration required')
    original=record.signal[:,channel]
    filtered,safe=filter_continuous(original,fs,config)
    table=record.annotations.copy()
    table=table.rename(columns={'record':'record_id','sample':'annotation_sample','symbol':'original_label','aami_group':'mapped_label'})
    table['subject_id']=subject; table['split']=split; table['lead']=lead; table['lead_channel']=channel
    table['sample_id']=[f'{record.name}:{i}' for i in table.annotation_index]
    table['window_start_sample']=table.annotation_sample-pre
    table['window_stop_sample_exclusive']=table.annotation_sample+post+1
    table['window_start_s']=table.window_start_sample/fs
    table['window_last_sample_s']=(table.window_stop_sample_exclusive-1)/fs
    table['fs_hz']=fs; table['unit']='mV'; table['center_index']=pre; table['window_length']=pre+post+1
    label_lookup={group:i for i,group in enumerate(groups)}
    table['target_label']=table.mapped_label.map(label_lookup).fillna(-1).astype(int)
    table['is_target']=table.mapped_label.isin(groups)
    table['included']=False; table['exclusion_reason']='not_target_group'; table['quality_flags']=''
    table.loc[table.annotation_kind=='non_beat','exclusion_reason']='non_beat_annotation'
    table.loc[table.annotation_kind.isin(['unknown','unmapped_beat']),'exclusion_reason']='unknown_or_unmapped_annotation'
    # A duplicate check only within target beats avoids confusing a coincident rhythm marker with a beat.
    target=table[table.is_target]
    duplicate_samples=set(target.loc[target.annotation_sample.duplicated(keep=False),'annotation_sample'])
    event_samples=record.annotations.loc[record.annotations.symbol.isin(['~','|']),'sample'].to_numpy()
    bits=record.header.adc_res[channel]; zero=record.header.adc_zero[channel]
    rail_low=zero-2**(bits-1); rail_high=zero+2**(bits-1)-1
    accepted=[]; raw_windows=[]; filtered_windows=[]
    for index,row in table[table.is_target].iterrows():
        start,stop,sample=int(row.window_start_sample),int(row.window_stop_sample_exclusive),int(row.annotation_sample)
        reason=''
        if sample in duplicate_samples: reason='duplicate_target_beat_position'
        elif start<0 or stop>len(original): reason='window_boundary'
        elif not np.isfinite(original[start:stop]).all(): reason='nonfinite_raw_window'
        elif not np.isfinite(filtered[start:stop]).all(): reason='invalid_filtered_window'
        elif not safe[start:stop].all(): reason='filter_edge_or_gap_guard'
        elif np.std(original[start:stop])<=1e-8: reason='flat_raw_window'
        elif np.std(filtered[start:stop])<=1e-8: reason='flat_filtered_window'
        if reason:
            table.loc[index,'exclusion_reason']=reason
            continue
        wave=original[start:stop]; fw=filtered[start:stop]; flags=[]
        adc=record.digital[start:stop,channel]
        if ((adc<=rail_low)|(adc>=rail_high)).any(): flags.append('adc_rail_present')
        if np.max(np.abs(wave))>5 or np.ptp(wave)>8: flags.append('large_physical_amplitude')
        if ((event_samples>=start)&(event_samples<stop)).any(): flags.append('near_quality_or_artifact_event')
        table.loc[index,'included']=True; table.loc[index,'exclusion_reason']='included'
        table.loc[index,'quality_flags']=';'.join(flags)
        accepted.append(index); raw_windows.append(wave); filtered_windows.append(fw)
    if accepted:
        raw=np.stack(raw_windows); values=np.stack(filtered_windows)
        metrics=morphology_metrics(raw,values,fs,pre)
        for name,value in metrics.items(): table.loc[accepted,name]=value
        table.loc[accepted,'raw_peak_to_peak_mV']=np.ptp(raw,axis=1)
        table.loc[accepted,'filtered_peak_to_peak_mV']=np.ptp(values,axis=1)
        for index in accepted:
            flags=table.loc[index,'quality_flags'].split(';') if table.loc[index,'quality_flags'] else []
            if table.loc[index,'raw_filtered_correlation']<.90: flags.append('morphology_correlation_lt_0.90')
            ratio=table.loc[index,'filtered_raw_ptp_ratio']
            if ratio<.5 or ratio>1.5: flags.append('amplitude_ratio_outside_0.5_1.5')
            if abs(table.loc[index,'local_peak_shift_ms'])>10: flags.append('local_peak_shift_gt_10ms')
            table.loc[index,'quality_flags']=';'.join(flags)
    else:
        raw=np.empty((0,pre+post+1)); values=np.empty_like(raw)
    return table,values.astype(np.float32),raw,filtered,np.asarray(accepted,dtype=int)
