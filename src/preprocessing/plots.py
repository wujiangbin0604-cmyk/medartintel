"""Training-only waveform audits plus prespecified aggregate split diagnostics."""
from pathlib import Path
import textwrap
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.signal import sosfreqz
from ..visuals.common import COLORS
from .filters import FilterConfig
from .normalization import transform


class Figures:
    def __init__(self,root): self.root=root; self.entries=[]

    def save(self,fig,name,title,scope,meaning):
        path=self.root/'figures/preprocessing'/f'{name}.png'
        path.parent.mkdir(parents=True,exist_ok=True)
        fig.suptitle(title,fontsize=13)
        fig.text(.015,.01,'\n'.join(textwrap.wrap(scope,150)),fontsize=7,va='bottom',color='#4c5661')
        fig.tight_layout(rect=(0,.065,1,.94)); fig.savefig(path,dpi=300); plt.close(fig)
        self.entries.append({'file':path.relative_to(self.root).as_posix(),'title':title.replace('\n',' / '),'scope':scope,'meaning':meaning})
        print(f'Plot {path.name}',flush=True)


def generate_figures(root,metadata,values,normalizer,contexts,tables,protocol):
    book=Figures(root); time=np.arange(-108,145)/360
    training=metadata[metadata.included & (metadata.split=='train')]
    for record_id,context in contexts.items():
        record=context['record']; channel=context['channel']; lead=record.leads[channel]
        raw=record.signal[:,channel]; filtered=context['filtered']; fs=record.fs
        start,stop=round(60*fs),round(70*fs); t=np.arange(start,stop)/fs
        fig,axes=plt.subplots(3,1,figsize=(12,7),sharex=True)
        axes[0].plot(t,raw[start:stop],lw=.8,c='#34465b',label='Raw physical ECG')
        axes[1].plot(t,filtered[start:stop],lw=.8,c='#2f8794',label='0.5-40Hz, forward-backward SOS')
        axes[2].plot(t,raw[start:stop]-filtered[start:stop],lw=.8,c='#bf7440',label='Raw minus filtered (removed components)')
        for ax in axes: ax.set_ylabel(f'{lead} (mV)'); ax.legend(loc='upper right',fontsize=8)
        axes[-1].set_xlabel('Time from record start (s)')
        scope=f'TRAIN ONLY; record={record_id}; lead={lead}; fs={fs:g}Hz; samples=[{start},{stop}); time=60-70s'
        book.save(fig,f'{record_id}_raw_filtered',f'Training record {record_id} | raw, filtered and residual',scope,
                  '比较滤波前后基线与细碎起伏；残差不是纯噪声，也可能含真实波形分量，不能宣称形态完全无失真。')
        part=training[(training.record_id==record_id)&(training.time_s>60)]
        rows=[]
        for group in ('N','V'):
            subgroup=part[part.mapped_label==group]
            if len(subgroup): rows.append(subgroup.iloc[0])
        for row in rows:
            sample=int(row.annotation_sample); start=int(row.window_start_sample); stop=int(row.window_stop_sample_exclusive)
            fig,ax=plt.subplots(figsize=(10,4.5))
            ax.plot(time,raw[start:stop]-np.median(raw[start:stop]),c='#626c78',lw=1,label='Raw minus window median (comparison only)')
            for label,signal in context['alternatives'].items(): ax.plot(time,signal[start:stop],lw=1.1,label=label)
            ax.axvline(0,c='#444b54',ls='--',lw=.8); ax.set_xlabel('Time relative to ORIGINAL expert annotation (s)'); ax.set_ylabel(f'{lead} (mV)'); ax.legend(fontsize=8)
            scope=f'TRAIN ONLY; {record_id}/{lead}; raw={row.original_label}->{row.mapped_label}; sample={sample}; t={row.time_s:.6f}s; window=[{start},{stop})'
            book.save(fig,f'{record_id}_{row.mapped_label}_filter_settings',f'Training record {record_id} | {row.mapped_label} | different fixed passbands',scope,
                      '比较预先指定的 0.5–40、0.5–45、1–40 Hz；默认仍为预先声明的 0.5–40 Hz，不利用验证/测试波形选频段。')
        if len(rows):
            row=rows[0]; sample=int(row.annotation_sample)
            start=max(0,sample-round(.8*fs)); stop=min(len(raw),sample+round(.8*fs))
            fig,axes=plt.subplots(2,1,figsize=(11,6))
            axes[0].plot(np.arange(start,stop)/fs,raw[start:stop],lw=.8,label='Raw ECG context')
            axes[0].axvspan((sample-108)/fs,(sample+144)/fs,color='#69a9b0',alpha=.25,label='253 samples, -0.3s to +0.4s')
            axes[0].axvline(sample/fs,c='#bd3c50',ls='--',label='Original annotation')
            axes[0].set_xlabel('Time from record start (s)'); axes[0].set_ylabel(f'{lead} (mV)'); axes[0].legend(fontsize=8)
            axes[1].plot(np.arange(253),filtered[sample-108:sample+145],color=COLORS[row.mapped_label],label='Exported filtered window')
            axes[1].axvline(108,c='#bd3c50',ls='--',label='Annotation at index 108')
            axes[1].set_xlabel('Window sample index (0..252)'); axes[1].set_ylabel(f'{lead} (mV)'); axes[1].legend(fontsize=8)
            book.save(fig,f'{record_id}_window_extraction',f'Training record {record_id} | fixed heartbeat extraction',
                      f'TRAIN ONLY; {record_id}/{lead}; annotation_sample={sample}; time={row.time_s:.6f}s; fs=360Hz',
                      '窗口含前 108 点、中心 1 点、后 144 点，共 253 点；不重新检测或移动专家标注，原始信号保持不变。')
    fig,ax=plt.subplots(figsize=(10,4.5))
    for config in (FilterConfig(),FilterConfig(.5,45.),FilterConfig(1.,40.)):
        f,h=sosfreqz(config.coefficients(360),worN=8192,fs=360)
        ax.plot(f,20*np.log10(np.maximum(np.abs(h)**2,1e-10)),label=f'{config.low_hz:g}-{config.high_hz:g}Hz')
    ax.set_xlim(0,80); ax.set_ylim(-80,3); ax.set_xlabel('Frequency (Hz)'); ax.set_ylabel('Forward-backward amplitude gain (dB)'); ax.legend()
    book.save(fig,'fixed_filter_frequency_response','Prespecified Butterworth SOS filters | effective two-pass response',
              'All 48 records use fs=360Hz; coefficient choices fixed before waveform comparison; no learned parameters',
              '双向滤波的幅值响应为单程 |H|²，角频点衰减约 -6 dB；零相位并不等于零幅值失真。')
    fig,axes=plt.subplots(2,3,figsize=(12,6),sharex=True)
    selected=[]
    for row_index,group in enumerate(('N','V')):
        part=training[training.mapped_label==group]
        # One actual sample from each of up to three training records, deterministically chosen.
        choices=part.groupby('record_id',sort=True).head(1).head(3)
        for ax,(_,row) in zip(axes[row_index],choices.iterrows()):
            vector=transform(values[int(row.global_row)],normalizer)
            ax.plot(time,vector,color=COLORS[group],label=f'{row.original_label}->{group}')
            ax.axvline(0,ls='--',c='#747b83',lw=.7); ax.set_title(f'{row.record_id}/{row.lead} | #{row.annotation_sample}\n{row.time_s:.3f}s | TRAIN',fontsize=9)
            ax.set_xlabel('Relative time (s)'); ax.set_ylabel('Training-standardized amplitude (z)'); ax.legend(fontsize=8)
            selected.append(row)
    book.save(fig,'processed_NV_examples','Processed N/V examples | different training records',
              'TRAIN ONLY; fixed 0.5-40Hz filter; global TRAIN-only mean/std; sample IDs shown in panels',
              '处理后的真实样本保持原始类别与位置；N 组含束支阻滞/部分逸搏，不能将所有 N 组样本称作正常。')
    fig,axes=plt.subplots(2,2,figsize=(11,6),sharex=True)
    for row_index,group in enumerate(('N','V')):
        row=training[training.mapped_label==group].iloc[0]; vector=values[int(row.global_row)]
        axes[row_index,0].plot(time,vector,c=COLORS[group],label=f'{row.record_id}/{row.lead}, {group}')
        axes[row_index,1].plot(time,transform(vector,normalizer),c=COLORS[group],label=f'#{row.annotation_sample}, {row.time_s:.3f}s')
        for col in range(2):
            axes[row_index,col].set_xlabel('Relative time (s)'); axes[row_index,col].legend(fontsize=8)
        axes[row_index,0].set_ylabel('Filtered amplitude (mV)'); axes[row_index,1].set_ylabel('Training-standardized amplitude (z)')
    axes[0,0].set_title('Before normalization'); axes[0,1].set_title('After the same global TRAIN transformation')
    book.save(fig,'normalization_before_after','N/V normalization | TRAIN-derived mean and standard deviation',
              f'TRAIN ONLY; mean={normalizer["mean_mV"]:.8f}mV; SD={normalizer["std_mV"]:.8f}mV; each row is the same sample before/after',
              '所有样本使用同一个训练集均值/标准差；没有为每个心拍缩放振幅，也没有用验证或测试集拟合。')
    counts=tables['split_class_counts'].pivot(index='split',columns='mapped_label',values='sample_count').reindex(['train','val','test'])
    fig,axes=plt.subplots(1,2,figsize=(11,5))
    for ax,frame,title in ((axes[0],counts,'Actual sample counts'),(axes[1],counts.div(counts.sum(axis=1),axis=0)*100,'Within-split percentage')):
        bottom=np.zeros(len(frame))
        for group in frame.columns:
            ax.bar(frame.index,frame[group],bottom=bottom,color=COLORS[group],label=group)
            for i,v in enumerate(frame[group]):
                if v: ax.text(i,bottom[i]+v/2,f'{v:.2f}%' if ax is axes[1] else str(int(v)),ha='center',va='center',fontsize=9)
            bottom+=frame[group].to_numpy()
        ax.set_title(title); ax.set_xlabel('Subject-independent split'); ax.set_ylabel('Beats' if ax is axes[0] else 'Beats (%)'); ax.legend(title='AAMI')
    book.save(fig,'split_class_distribution','All 48 records | accepted classes after subject-independent splitting',
              'Aggregate labels/counts only; no held-out waveform used for method selection; exact records in split_manifest.csv',
              '约 70/15/15 分配的是受试者数，心拍数量比例不一定相同；验证和测试保留自然类别分布，没有重采样。')
    subjects=metadata[metadata.included].groupby(['subject_id','split']).size().reset_index(name='n')
    v=metadata[metadata.included & (metadata.mapped_label=='V')].groupby('subject_id').size()
    subjects['V']=subjects.subject_id.map(v).fillna(0).astype(int); subjects=subjects.sort_values(['split','n'],ascending=[True,False])
    fig,axes=plt.subplots(1,2,figsize=(12,max(7,len(subjects)*.23)),sharey=True)
    split_colors={'train':'#327c89','val':'#c78a26','test':'#9762a8'}
    positions=np.arange(len(subjects)); colors=[split_colors[s] for s in subjects.split]
    axes[0].barh(positions,subjects.n,color=colors); axes[1].barh(positions,subjects.V,color=colors)
    axes[0].set_yticks(positions,[s.replace('subject_','') for s in subjects.subject_id],fontsize=7); axes[0].invert_yaxis()
    axes[0].set_ylabel('Subject group ID (201/202 combined)'); axes[0].set_xlabel('Accepted target beats'); axes[1].set_xlabel('Accepted V beats')
    from matplotlib.patches import Patch
    axes[0].legend(handles=[Patch(color=c,label=s) for s,c in split_colors.items()],fontsize=8)
    book.save(fig,'subject_sample_counts','Samples per independent subject | total and V counts',
              'All 47 subject groups; 48 records; labels/counts only; group IDs are pseudonyms, not clinical patient identifiers',
              '显示不同受试者贡献量及 V 类覆盖；201/202 合并，不可拆到不同集合；图中差异不用于改变测试采样。')
    technical=metadata[metadata.is_target & ~metadata.included].exclusion_reason.value_counts()
    excluded=metadata[~metadata.is_target].exclusion_reason.value_counts()
    flags=metadata.loc[metadata.included,'quality_flags'].str.split(';').explode(); flags=flags[flags!=''].value_counts()
    fig,axes=plt.subplots(1,3,figsize=(15,5))
    for ax,series,title in zip(axes,(excluded,technical,flags),('Labels outside current task','Technical/boundary exclusions','Quality flags: KEPT, may overlap')):
        if len(series):
            bars=ax.barh(np.arange(len(series)),series.to_numpy(),color='#bd6e53')
            ax.set_yticks(np.arange(len(series)),[name.replace('_',' ') for name in series.index],fontsize=7)
            ax.bar_label(bars,padding=3,fontsize=8); ax.invert_yaxis(); ax.set_xlim(0,series.max()*1.25)
        else: ax.text(.5,.5,'None',transform=ax.transAxes,ha='center')
        ax.set_title(title,fontsize=10); ax.set_xlabel('Annotation / window count'); ax.set_ylabel('Reason / review flag')
    book.save(fig,'exclusions_and_quality_flags','Non-target labels, invalid windows and retained review flags',
              'All records; fixed technical rules; quality flags do not change labels or remove samples',
              '前两栏是互斥主排除原因；右栏是保留样本上的可重叠复核标记，不能相加当作排除总数。')
    fig,axes=plt.subplots(1,3,figsize=(13,4.5))
    for group in ('N','V'):
        part=training[training.mapped_label==group]
        for ax,column,label in zip(axes,('raw_filtered_correlation','filtered_raw_ptp_ratio','local_peak_shift_ms'),
                                   ('Raw/filtered window correlation','Filtered/raw peak-to-peak ratio','Local dominant-peak shift (ms)')):
            ax.hist(part[column].dropna(),bins=50,histtype='step',color=COLORS[group],label=group,linewidth=1.4)
            ax.set_xlabel(label,fontsize=9); ax.set_ylabel('Training beat count'); ax.legend()
    book.save(fig,'training_filter_morphology_audit','TRAIN ONLY | morphology change under the fixed 0.5-40Hz filter',
              'All accepted training N/V windows; expert annotation positions retained; local peak search limited to +/-80ms for diagnostics',
              '滤波相关性、幅值比与局部极值偏移只是工程形态变化指标，不能证明临床形态无失真；没有据此移动标签或自动删除样本。')
    return pd.DataFrame(book.entries)
