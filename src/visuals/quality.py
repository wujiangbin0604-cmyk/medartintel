import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from .common import COLORS
from ..labels import GROUPS


def baseline_windows(record,seconds=10):
    """One-second block medians; a descriptive baseline/amplitude variation proxy."""
    rows=[]
    fs=round(record.fs); step=round(seconds*record.fs)
    for channel,lead in enumerate(record.leads):
        for start in range(0,len(record.signal),step):
            stop=min(start+step,len(record.signal))
            medians=[np.median(record.signal[s:min(s+fs,stop),channel]) for s in range(start,stop,fs)]
            rows.append({'record':record.name,'lead':lead,'unit':record.units[channel],
                         'start_sample':start,'stop_sample_exclusive':stop,'start_s':start/record.fs,'end_s':stop/record.fs,
                         'block_median_range':float(np.ptp(medians)),'block_count':len(medians)})
    return pd.DataFrame(rows)


def baseline_strip(book,record,channel,start,stop,filename,purpose):
    lead=record.leads[channel]; fs=record.fs; x=record.signal[start:stop,channel]
    starts=list(range(start,stop,round(fs)))
    medians=np.array([np.median(record.signal[s:min(s+round(fs),stop),channel]) for s in starts])
    centers=np.array([(s+min(s+round(fs),stop)-1)/2/fs for s in starts])
    fig,axes=plt.subplots(2,1,figsize=(12,6),sharex=True)
    axes[0].plot(np.arange(start,stop)/fs,x,color='#283c52',lw=.7,label='Unfiltered physical ECG')
    axes[0].plot(centers,medians,c='#ca6e22',lw=2,marker='o',ms=3,label='1s block median (proxy only)')
    axes[0].set_ylabel(f'{lead} ({record.units[channel]})'); axes[0].legend(fontsize=8,loc='upper right')
    axes[1].plot(centers,medians,c='#ca6e22',marker='o',label='1s block median')
    axes[1].set_ylabel(f'Block median ({record.units[channel]})'); axes[1].set_xlabel('Time from record start (s)'); axes[1].legend(fontsize=8)
    book.save(fig,'E',filename,f'Record {record.name} | {lead} | baseline/amplitude drift candidate',purpose,
              f'区间 {start/fs:.3f}–{stop/fs:.3f} s；原始幅值 {x.min():.3f}–{x.max():.3f} {record.units[channel]}；1 s 块中位数范围 {np.ptp(medians):.3f} {record.units[channel]}。',
              '块中位数不是分离出的真实基线，也会受宽心拍和其他伪迹影响；本图不自动诊断漂移来源，不据此删样本。',
              f'record={record.name}; lead={lead}; samples=[{start},{stop}); fs={fs:g}Hz; relative time={start/fs:.3f}-{stop/fs:.3f}s')


def generate(book,beats,summary):
    labels=[f'{row.record}\n{row.lead}' for row in summary.itertuples()]
    leads=sorted(summary.lead.unique()); palette={lead:plt.get_cmap('tab10')(i) for i,lead in enumerate(leads)}
    colors=[palette[lead] for lead in summary.lead]
    fig,ax=plt.subplots(figsize=(max(10,min(24,len(summary)*.4)),5))
    ax.bar(labels,summary.maximum-summary.minimum,bottom=summary.minimum,color=colors,alpha=.75)
    for i,row in enumerate(summary.itertuples()):
        ax.text(i,row.maximum,f'{row.maximum:.2f}',ha='center',va='bottom',fontsize=8)
        ax.text(i,row.minimum,f'{row.minimum:.2f}',ha='center',va='top',fontsize=8)
    ax.axhline(0,color='#545c66',lw=.8); ax.margins(y=.2)
    ax.set_xlabel('Record ID / lead'); ax.set_ylabel('Physical amplitude min to max (mV)')
    ax.legend(handles=[Patch(color=palette[l],label=l) for l in leads],title='Lead',ncol=min(5,len(leads)))
    book.save(fig,'E','record_amplitude_ranges','All records and leads | observed amplitude range',
              '逐记录、逐导联比较原始幅值的最小至最大范围。',
              '；'.join(f'{r.record}/{r.lead}: {r.minimum:.3f}–{r.maximum:.3f} {r.unit}' for r in summary.itertuples()),
              '全局极值可能来自一个短片段；幅值大不必然是疾病或噪声，必须回看具体时间。')
    fig,ax=plt.subplots(figsize=(max(10,min(24,len(summary)*.4)),5))
    bars=ax.bar(labels,summary['std'],color=colors,alpha=.8); ax.bar_label(bars,fmt='%.3f',padding=4)
    ax.set_ylim(0,summary['std'].max()*1.2); ax.set_xlabel('Record ID / lead'); ax.set_ylabel('Whole-record signal standard deviation (mV)')
    ax.legend(handles=[Patch(color=palette[l],label=l) for l in leads],title='Lead')
    book.save(fig,'E','record_signal_std','All records and leads | signal standard deviation',
              '比较完整信号的总变异强度，作为质量复核线索。',
              '；'.join(f'{r.record}/{r.lead}: SD={r.std:.4f} {r.unit}' for r in summary.itertuples()),
              '标准差同时受心拍幅值、心率、基线与噪声影响，不是验证过的信号质量评分。')
    statuses=['valid','left','right','both','nonfinite','unmapped']
    table=beats.groupby(['record','extraction_status']).size().unstack(fill_value=0).reindex(columns=statuses,fill_value=0)
    fig,axes=plt.subplots(1,2,figsize=(12,5))
    bottom=np.zeros(len(table)); status_colors=['#3b8290','#de8c36','#c24754','#8756a7','#616975','#a3aab3']
    for status,color in zip(statuses,status_colors):
        axes[0].bar(table.index,table[status],bottom=bottom,label=status,color=color); bottom+=table[status].to_numpy()
    rejected=table.drop(columns='valid')
    bottom=np.zeros(len(rejected))
    for status,color in zip(statuses[1:],status_colors[1:]):
        bars=axes[1].bar(rejected.index,rejected[status],bottom=bottom,label=status,color=color)
        for i,v in enumerate(rejected[status]):
            if v: axes[1].text(i,bottom[i]+v/2,str(v),ha='center',va='center',fontsize=10)
        bottom+=rejected[status].to_numpy()
    for ax in axes:
        ax.set_xlabel('Record ID'); ax.set_ylabel('Heartbeat-window count'); ax.legend(fontsize=8)
    axes[0].set_title('All recognized beats'); axes[1].set_title('Rejected windows only (expanded scale)')
    book.tables['extraction_status_by_record']=table.reset_index()
    book.save(fig,'E','window_boundary_accounting','Heartbeat extraction | boundary and validity accounting',
              '说明全心拍统计与可视化可用窗口之间的差别，显式审计边界丢失。',
              f'共 {len(beats)} 个已识别心拍；有效映射窗口 {int((beats.extraction_status=="valid").sum())}；'+
              '；'.join(f'{s}={int((beats.extraction_status==s).sum())}' for s in statuses[1:]),
              '越界、非有限或未映射的窗口不用于形态/降维，但其原始标注和计数仍保留；valid 不等于信号质量良好。')
    candidates=[]
    for record in book.records:
        windows=baseline_windows(record); candidates.append(windows)
        for lead,part in windows.groupby('lead'):
            row=part.loc[part.block_median_range.idxmax()]
            channel=record.leads.index(lead)
            if row.block_median_range>=.5 and record.units[channel]=='mV':
                baseline_strip(book,record,channel,int(row.start_sample),int(row.stop_sample_exclusive),
                               f'{record.name}_{lead}_largest_baseline_variation','展示块中位数变化最大的候选片段，阈值仅为可视化选择规则（≥0.5 mV）。')
        # Expert quality-change context adds a different, annotation-driven selection criterion.
        events=record.annotations[(record.annotations.symbol=='~')&(record.annotations.time_s>1)]
        if len(events):
            center=events.iloc[0].time_s
            channel=len(record.leads)-1
            baseline_strip(book,record,channel,max(0,round((center-2)*record.fs)),min(len(record.signal),round((center+8)*record.fs)),
                           f'{record.name}_{record.leads[channel]}_quality_event_baseline',
                           '展示第一处非初始专家信号质量变化事件附近的最后一个导联，观察低频漂移与心拍可辨性。')
    book.tables['baseline_variation_windows']=pd.concat(candidates,ignore_index=True)
