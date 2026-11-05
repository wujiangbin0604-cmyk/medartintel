import matplotlib.pyplot as plt
from matplotlib.patches import Patch
import numpy as np
import pandas as pd
from .common import COLORS, heatmap
from ..labels import GROUPS


def generate(book, annotations, tables):
    raw, totals, by_record = tables['raw_symbol_counts'], tables['aami_counts'], tables['aami_counts_by_record']
    n = int(totals['count'].sum())
    for name, part in [('all_records', annotations)] + [(r.name, r.annotations) for r in book.records]:
        display_name=', '.join(r.name for r in book.records) if name=='all_records' else name
        counts = part.groupby(['symbol','annotation_kind']).size().reset_index(name='count').sort_values('count', ascending=False)
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
        colors = [COLORS.get(str(part.loc[part.symbol == s, 'aami_group'].iloc[0]), '#9da4ad') for s in counts.symbol]
        for ax in axes:
            bars = ax.bar(counts.symbol, counts['count'], color=colors)
            ax.bar_label(bars, fontsize=8, padding=3)
            ax.set_xlabel('Original annotation.symbol (case sensitive)')
            ax.set_ylabel('All annotation events')
            ax.set_ylim(0, counts['count'].max() * 1.18)
        axes[0].set_title('Linear scale')
        shown=[g for g in GROUPS if (part.aami_group==g).any()]
        axes[0].legend(handles=[Patch(color=COLORS[g],label=f'AAMI {g}') for g in shown]+[Patch(color='#9da4ad',label='Non-beat / unmapped')],fontsize=8,loc='upper right')
        axes[1].set_yscale('log')
        axes[1].set_ylim(.7, counts['count'].max() * 2)
        axes[1].set_title('Log scale reveals rare symbols')
        nonbeat = int((part.annotation_kind == 'non_beat').sum())
        finding = '；'.join(f"原始 {row.symbol}={row.count}" for row in counts.itertuples()) + f'。其中非心拍事件 {nonbeat} 条。'
        book.save(fig,'A',f'{name}_raw_symbol_counts',f'Records {display_name} | original annotation frequency',
                  '比较全部原始符号，区分心拍与节律/质量等非心拍事件。',finding,
                  '非心拍符号不能计入 AAMI 心拍分布；柱的颜色仅提示已有分组，灰色为非五组项。')
    values = totals.set_index('aami_group').reindex(GROUPS)['count']
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(GROUPS, values, color=[COLORS[g] for g in GROUPS])
    ax.bar_label(bars, padding=4)
    ax.set_ylim(0, max(values.max() * 1.2,1))
    ax.set_xlabel('AAMI group'); ax.set_ylabel('Mapped heartbeat count')
    finding = '；'.join(f'{g}={int(values[g])} 拍' for g in GROUPS)
    book.save(fig,'A','aami_counts','All selected records | AAMI five-group counts',
              '识别多数类、稀有类与零样本类。',finding,'分母只包含已映射心拍；N 组不等同于全部医学正常。')
    fig, ax = plt.subplots(figsize=(9, 6))
    positive = values[values > 0]
    if n:
        wedges, _ = ax.pie(positive, colors=[COLORS[g] for g in positive.index], startangle=90,
                           wedgeprops={'edgecolor':'white', 'linewidth':1})
        ax.legend([Patch(color=COLORS[g]) for g in GROUPS],
                  [f'{g}: {int(values[g])} ({values[g]/n*100:.3f}%)' for g in GROUPS],loc='center left',bbox_to_anchor=(1,.5))
    ax.set_xlabel('Share of mapped beats; zero-count groups have no wedge')
    ax.set_ylabel('Five-group composition (area fraction)')
    book.save(fig,'A','aami_pie','All selected records | AAMI proportions',
              '用整体占比展示类别不平衡，同时在图例保留稀有类精确比例。',
              '；'.join(f'{g}={values[g]/n*100:.4f}%' for g in GROUPS) if n else '无已映射心拍。',
              '小扇区不容易目视比较，数量请结合柱图；零样本组：'+','.join(values[values==0].index))
    pivot = by_record.pivot(index='record', columns='aami_group', values='count').reindex(columns=GROUPS, fill_value=0)
    percentages = pivot.div(pivot.sum(axis=1).replace(0,np.nan), axis=0) * 100
    for name, frame, ylabel in [('record_class_stacked',pivot,'Mapped beat count'),('record_class_percentage',percentages,'Within-record mapped beats (%)')]:
        fig,ax=plt.subplots(figsize=(max(9,min(22,len(pivot)*.42)),5))
        bottom=np.zeros(len(frame))
        for group in GROUPS:
            ax.bar(frame.index,frame[group],bottom=bottom,color=COLORS[group],label=group)
            bottom+=frame[group].fillna(0).to_numpy()
        ax.legend(title='AAMI',ncol=5,loc='upper right'); ax.set_xlabel('Record ID'); ax.set_ylabel(ylabel)
        if len(frame)>10: ax.tick_params(axis='x',rotation=90)
        book.save(fig,'A',name,'Record comparison | '+ylabel,
                  '比较记录之间的样本量和类别构成，观察记录效应。',
                  '；'.join(f"记录 {r}: "+', '.join(f'{g}={pivot.loc[r,g]}' for g in GROUPS) for r in pivot.index),
                  '记录长短或心率会影响计数；百分比不能代表人群患病率。')
    fig,axes=plt.subplots(1,2,figsize=(12,max(4.5,len(pivot)*.25)))
    heatmap(axes[0],np.log10(1+pivot),pivot.index,GROUPS,'log10(1+beat count)',formatter='.2f')
    heatmap(axes[1],percentages,pivot.index,GROUPS,'Within-record (%)',limits=(0,100),formatter='.2f')
    for ax in axes: ax.set_xlabel('AAMI group'); ax.set_ylabel('Record ID')
    axes[0].set_title('Log count'); axes[1].set_title('Record-normalized percentage')
    book.save(fig,'A','record_class_heatmap','Record x class | count and within-record percentage',
              '同时观察绝对频数和记录内构成，减少大类遮蔽稀有类的问题。',
              f'矩阵为 {len(pivot)} 条记录 × 5 类；零计数单元格 {int((pivot==0).sum().sum())} 个。',
              '左图数值为 log10(1+count)，不是原始次数；右图各行合计 100%。')
    ranking=(100-percentages['N']).sort_values(ascending=False)
    fig,ax=plt.subplots(figsize=(10,max(4.5,len(ranking)*.25)))
    bars=ax.barh(ranking.index,ranking,color=COLORS['V']); ax.invert_yaxis()
    ax.bar_label(bars,fmt='%.2f%%',padding=5); ax.set_xlim(0,max(5,ranking.max()*1.2))
    ax.set_xlabel('Non-N groups / all mapped beats (%)'); ax.set_ylabel('Record ID')
    ranking_table=ranking.rename('non_n_percentage').reset_index()
    book.tables['non_n_record_ranking']=ranking_table
    book.save(fig,'A','record_non_n_ranking','Records ranked by non-N beat proportion',
              '按操作性定义比较各记录的非 N 组比例。',
              '；'.join(f'{r}: {v:.3f}%' for r,v in ranking.items()),
              '这是 S/V/F/Q 占已映射心拍比例；N 组含部分非正常心拍，Q 含起搏/不确定心拍，因此不能视作临床异常患病率。')
