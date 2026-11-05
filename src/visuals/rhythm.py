import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from .common import COLORS
from ..labels import GROUPS


def generate(book,beats):
    stats=[]
    for name,part in [('all_records',beats)]+[(r.name,beats[beats.record==r.name]) for r in book.records]:
        display_name=', '.join(r.name for r in book.records) if name=='all_records' else name
        rr=part.rr_previous_s.dropna().to_numpy()
        fig,ax=plt.subplots(figsize=(10,4.8))
        ax.hist(rr,bins=50,color='#397c8b',edgecolor='white',lw=.4,label=f'All intervals, n={len(rr)}')
        if len(rr): ax.axvline(np.median(rr),ls='--',c='#be3648',label=f'Median {np.median(rr):.3f}s')
        ax.set_xlabel('Previous RR interval (s)'); ax.set_ylabel('Interval count'); ax.legend()
        finding=f'有效 RR={len(rr)}；'+(f'范围 {rr.min():.4f}–{rr.max():.4f} s，中位数 {np.median(rr):.4f} s。' if len(rr) else '没有可用 RR。')
        book.save(fig,'D',f'{name}_rr_histogram',f'Records {display_name} | RR distribution',
                  '观察原始专家心拍间隔的分布宽度与多峰结构。',finding,
                  'RR 来自相邻已识别心拍的标注间隔，不跨记录拼接；包含异位心拍，不是仅正常 NN 间期或临床 HRV 分析。')
        mapped=part[(part.aami_group!='') & part.rr_previous_s.notna() & part.rr_next_s.notna()]
        fig,ax=plt.subplots(figsize=(7,6))
        for group in GROUPS:
            frame=mapped[mapped.aami_group==group]
            if not frame.empty: ax.scatter(frame.rr_previous_s,frame.rr_next_s,s=12,c=COLORS[group],alpha=.45,label=f'{group}, n={len(frame)}')
        if len(mapped):
            maximum=max(mapped.rr_previous_s.max(),mapped.rr_next_s.max())*1.05
            ax.plot([0,maximum],[0,maximum],ls='--',lw=.8,c='#6f7780',label='Previous = next')
            ax.set_xlim(0,maximum); ax.set_ylim(0,maximum)
        ax.set_xlabel('Previous RR (s)'); ax.set_ylabel('Next RR (s)'); ax.legend(fontsize=8); ax.set_aspect('equal',adjustable='box')
        summaries=[]
        for group,frame in mapped.groupby('aami_group'):
            summaries.append(f'{group}: n={len(frame)}, 前/后 RR 中位数={frame.rr_previous_s.median():.4f}/{frame.rr_next_s.median():.4f} s')
        book.save(fig,'D',f'{name}_previous_next_rr',f'Records {display_name} | previous RR versus next RR, colored by current beat',
                  '检查当前心拍前后节律上下文和局部时间关系。','；'.join(summaries),
                  '颜色来自当前拍原始标签的 AAMI 映射；首末拍缺少邻居会被排除，但不因此删去原始计数；不按散点位置重标注。')
    for record in book.records:
        part=beats[beats.record==record.name]
        rr=part.rr_previous_s.dropna()
        stats.append({'record':record.name,'interval_count':len(rr),'mean_rr_s':rr.mean(),'std_rr_s':rr.std(ddof=0),
                      'median_rr_s':rr.median(),'min_rr_s':rr.min(),'max_rr_s':rr.max()})
        fig,ax=plt.subplots(figsize=(13,4.5))
        ax.plot(part.time_s,part.rr_previous_s,color='#86909b',lw=.5,alpha=.6,label='Successive RR')
        for group in GROUPS:
            frame=part[(part.aami_group==group)&part.rr_previous_s.notna()]
            if len(frame): ax.scatter(frame.time_s,frame.rr_previous_s,s=7,c=COLORS[group],label=group,alpha=.5)
        ax.set_xlabel('Current beat time from record start (s)'); ax.set_ylabel('Previous RR (s)'); ax.legend(ncol=6,fontsize=8,loc='upper right')
        book.save(fig,'D',f'{record.name}_rr_over_time',f'Record {record.name} | RR interval over the full record',
                  '定位短长间隔和节律变化发生的时间。',
                  f'{len(rr)} 个间隔；均值 {rr.mean():.4f} s，标准差 {rr.std(ddof=0):.4f} s；未做生理阈值裁剪。',
                  '曲线由相邻事件连接，不是连续测量的瞬时 RR；包含异位心拍，不能直接解释为自主神经功能。',
                  f'record={record.name}; annotation stream on all leads; time=0-{record.duration:.3f}s; fs={record.fs:g}Hz')
    table=pd.DataFrame(stats); book.tables['rr_statistics']=table
    fig,ax=plt.subplots(figsize=(max(9,min(22,len(table)*.45)),5))
    bars=ax.bar(table.record,table.mean_rr_s,yerr=table.std_rr_s,capsize=4,color='#3b8290',alpha=.85,label='Mean +/- SD of RR intervals')
    ax.bar_label(bars,labels=[f'{v:.3f}s' for v in table.mean_rr_s],padding=5)
    ax.set_xlabel('Record ID'); ax.set_ylabel('RR interval (s)'); ax.legend()
    if len(table)>10: ax.tick_params(axis='x',rotation=90)
    book.save(fig,'D','record_mean_rr','Each record | mean and standard deviation of RR',
              '比较不同记录的平均心拍间隔和分散程度。',
              '；'.join(f'{row.record}: 均值 {row.mean_rr_s:.4f} s，SD {row.std_rr_s:.4f} s，n={row.interval_count}' for row in table.itertuples()),
              '误差线为该记录间隔的标准差，不是受试者间差异或均值置信区间。')
