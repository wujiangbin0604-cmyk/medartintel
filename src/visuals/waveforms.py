import matplotlib.pyplot as plt
import numpy as np
from .common import COLORS
from ..analysis import primary_channel
from ..labels import GROUPS


def strip(book, record, start_s, end_s, filename, mode='class', reason='前 10 秒观察'):
    start=max(0,round(start_s*record.fs)); stop=min(len(record.signal),round(end_s*record.fs))
    table=record.annotations[(record.annotations['sample']>=start)&(record.annotations['sample']<stop)]
    beats=table[table.annotation_kind.isin(['mapped_beat','unmapped_beat'])]
    fig,axes=plt.subplots(len(record.leads),1,figsize=(13,3*len(record.leads)),sharex=True,squeeze=False)
    for channel,lead in enumerate(record.leads):
        ax=axes[channel,0]
        ax.plot(np.arange(start,stop)/record.fs,record.signal[start:stop,channel],lw=.8,color='#263b52',label='Raw ECG')
        if mode=='position':
            samples=beats['sample'].to_numpy(dtype=int)
            ax.scatter(samples/record.fs,record.signal[samples,channel],s=20,c='#cf6a24',label='Expert beat position',zorder=3)
            for row in beats.itertuples():
                ax.annotate(row.symbol,(row.time_s,record.signal[row.sample,channel]),xytext=(0,9),textcoords='offset points',ha='center',fontsize=8)
        elif mode=='class':
            for group in GROUPS:
                part=beats[beats.aami_group==group]
                if part.empty: continue
                samples=part['sample'].to_numpy(dtype=int)
                ax.scatter(samples/record.fs,record.signal[samples,channel],s=22,c=COLORS[group],label=f'AAMI {group}',zorder=3)
                for row in part.itertuples():
                    ax.annotate(row.symbol,(row.time_s,record.signal[row.sample,channel]),xytext=(0,9),textcoords='offset points',ha='center',fontsize=8,color=COLORS[group])
        if mode!='raw':
            for i,row in enumerate(table[table.annotation_kind=='non_beat'].itertuples()):
                ax.axvline(row.time_s,color='#80868d',ls=':',lw=.9,label='Non-beat event' if i==0 else None)
                ax.text(row.time_s,.95-.08*(i%2),row.symbol,transform=ax.get_xaxis_transform(),fontsize=8,color='#71777f')
        ax.margins(y=.2); ax.set_ylabel(f'{lead} ({record.units[channel]})')
        ax.set_title(f'Record {record.name} | lead {lead}',loc='left',fontsize=10)
        ax.legend(loc='lower right',bbox_to_anchor=(1,1.01),ncol=6,fontsize=8)
    axes[-1,0].set_xlabel('Time from record start (s)'); axes[-1,0].set_xlim(start/record.fs,stop/record.fs)
    counts=beats.aami_group.value_counts()
    finding=f'区间 [{start/record.fs:.3f}, {stop/record.fs:.3f}) s，{len(beats)} 个心拍；'+', '.join(f'{g}={int(counts.get(g,0))}' for g in GROUPS)
    scope=f'record={record.name}; leads={",".join(record.leads)}; fs={record.fs:g}Hz; samples=[{start},{stop}); time=[{start/record.fs:.3f},{stop/record.fs:.3f})s'
    book.save(fig,'B',filename,f'Record {record.name} | {mode} | {start/record.fs:.3f}-{stop/record.fs:.3f}s',
              reason+'；对照原始波形、专家位置与类别。',finding,
              '标注位置直接来自 .atr，不保证是每个导联上的精确 R 峰；同一标注重复显示在各导联，但心拍只统计一次。',scope)


def generate(book,collections):
    for record in book.records:
        for mode in ('raw','position','class'):
            strip(book,record,0,10,f'{record.name}_first10_{mode}',mode)
        lead=record.leads[primary_channel(record)]
        collection=collections.get(lead)
        if collection is None: continue
        meta=collection.metadata[collection.metadata.record==record.name]
        for group in GROUPS:
            part=meta[meta.aami_group==group]
            if part.empty: continue
            center=part.iloc[len(part)//2].time_s
            strip(book,record,center-3,center+3,f'{record.name}_{lead}_{group}_context','class',
                  f'以 {group} 类时间排序的中间有效心拍为中心观察约 6 秒节律上下文')
    groups={}
    for record in book.records:
        lead=record.leads[primary_channel(record)]
        groups.setdefault(lead,[]).append(record)
    for lead,records in groups.items():
        if len(records)<2: continue
        for page in range(0,len(records),6):
            subset=records[page:page+6]
            fig,axes=plt.subplots(len(subset),1,figsize=(12,2.8*len(subset)),sharex=True,sharey=True,squeeze=False)
            findings=[]
            for ax,record in zip(axes[:,0],subset):
                channel=record.leads.index(lead); stop=min(round(10*record.fs),len(record.signal))
                ax.plot(np.arange(stop)/record.fs,record.signal[:stop,channel],color='#263b52',lw=.8,label=f'{record.name}/{lead}')
                ax.set_ylabel(f'ECG ({record.units[channel]})'); ax.legend(loc='upper right')
                ax.set_title(f'Record {record.name}; samples [0,{stop}); fs={record.fs:g}Hz',loc='left',fontsize=10)
                findings.append(f'{record.name}/{lead} 前 10 s 幅值范围 {record.signal[:stop,channel].min():.3f}–{record.signal[:stop,channel].max():.3f} {record.units[channel]}')
            axes[-1,0].set_xlabel('Time from each record start (s)')
            book.save(fig,'B',f'{lead}_record_comparison_page{page//6+1}',f'Record comparison | same lead {lead} | first 10 seconds',
                      '在同导联、同时间长度和相同纵轴尺度下比较记录差异。','；'.join(findings),
                      '不同记录属于不同受试者/记录背景，不按外观推断疾病；不把不同导联混为一种形态。',
                      '; '.join(f'{r.name}/{lead}:0-10s;fs={r.fs:g}Hz' for r in subset))
