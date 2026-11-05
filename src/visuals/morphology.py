import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from .common import COLORS, pool_scope, empty_panel, count_text
from ..heartbeat import random_generator
from ..labels import GROUPS


def representative_indices(collection,group,maximum=9):
    positions=np.flatnonzero(collection.metadata.aami_group.to_numpy()==group)
    if not len(positions): return positions
    centered=collection.centered[positions]
    target=centered.mean(axis=0)
    nearest=int(positions[np.argmin(np.mean((centered-target)**2,axis=1))])
    ranked=positions[np.argsort(collection.metadata.iloc[positions].peak_to_peak.to_numpy(),kind='stable')]
    selected=[nearest]
    for rank in np.linspace(0,len(ranked)-1,min(maximum,len(ranked)),dtype=int):
        value=int(ranked[rank])
        if value not in selected: selected.append(value)
        if len(selected)==maximum: break
    return np.array(selected,dtype=int)


def generate(book,collections):
    feature_summaries=[]
    for lead,collection in collections.items():
        meta,raw,time=collection.metadata,collection.raw,collection.time
        centered=collection.centered; scope=pool_scope(collection)
        for group in GROUPS:
            positions=np.flatnonzero(meta.aami_group.to_numpy()==group)
            rng=random_generator(book.config['seed'],'overlay',lead,group)
            selected=np.sort(rng.choice(positions,min(20,len(positions)),replace=False)) if len(positions) else positions
            filename=f'figures/C_morphology/{lead}_{group}_random20_overlay.png'
            fig,axes=plt.subplots(1,2,figsize=(12,4.8),sharex=True,sharey=True)
            for ax,values,label in zip(axes,(raw,centered),('Raw physical amplitude','Window-median centered (display only)')):
                for i,position in enumerate(selected):
                    ax.plot(time,values[position],alpha=.48,lw=.85,color=plt.get_cmap('tab20')(i%20))
                if not len(selected): empty_panel(ax,f'No {group} beats available',ylabel=f'{lead} ({collection.unit})')
                ax.axvline(0,c='#72777f',ls='--',lw=.8); ax.set_title(label,fontsize=10)
                ax.set_xlabel('Time relative to original beat annotation (s)'); ax.set_ylabel(f'{lead} amplitude ({collection.unit})')
            # Per-trace record/sample/time identifiers are kept in the selection CSV, not an unreadable 20-line legend.
            book.select(collection,selected,filename,f'without replacement; seed={book.config["seed"]}; group={group}')
            book.save(fig,'C',f'{lead}_{group}_random20_overlay',f'Lead {lead} | AAMI {group} | {len(selected)} randomly sampled beats',
                      '固定种子随机选取最多 20 拍，观察类内幅值、基线与形态变化。',
                      f'该导联 {group} 类有 {len(positions)} 个有效窗口，实际不放回抽取 {len(selected)} 个；样本标识见 plotted_heartbeat_windows.csv。',
                      '不足 20 拍时全部展示，不复制稀有类；不同颜色只区分抽样曲线，不代表额外类别。',scope)
            fig,ax=plt.subplots(figsize=(10,4.5))
            if len(positions):
                values=centered[positions]; mean=values.mean(axis=0); sd=values.std(axis=0)
                ax.fill_between(time,mean-sd,mean+sd,color=COLORS[group],alpha=.2,label='Mean +/- 1 SD (pointwise)')
                ax.plot(time,mean,c=COLORS[group],lw=1.8,label=f'{group}, n={len(positions)}')
                ax.legend(loc='upper right')
            else: empty_panel(ax,f'No {group} template: zero samples',ylabel=f'{lead} ({collection.unit})')
            ax.axvline(0,c='#72777f',ls='--',lw=.8); ax.set_xlabel('Time relative to original beat annotation (s)'); ax.set_ylabel(f'Median-centered {lead} ({collection.unit})')
            book.save(fig,'C',f'{lead}_{group}_mean_sd',f'Lead {lead} | AAMI {group} | class mean and variability',
                      '用全部有效窗口的平均波形和逐采样点标准差补充少量示例。',
                      f'模板使用 {len(positions)} 个窗口；'+(f'各点标准差最大值 {centered[positions].std(axis=0).max():.4f} {collection.unit}。' if len(positions) else '未生成虚构模板。'),
                      '阴影是类内逐点标准差，不是均值置信区间；先各窗减中位数，不缩放幅值，不重新定位峰。',scope)
            selected=representative_indices(collection,group)
            fig,axes=plt.subplots(3,3,figsize=(12,8),sharex=True,sharey=True)
            if not len(selected):
                empty_panel(axes[0,0],f'No {group} beats',ylabel=f'{lead} ({collection.unit})')
                for ax in axes.flat[1:]: ax.set_visible(False)
            else:
                for ax,position in zip(axes.flat,selected):
                    row=meta.iloc[position]
                    ax.plot(time,raw[position],color=COLORS[group],lw=1)
                    ax.axvline(0,c='#72777f',ls='--',lw=.6)
                    ax.set_title(f'{row.record}/{lead} | {row.symbol}->{group}\n#{int(row["sample"])} | {row.time_s:.3f}s',fontsize=8)
                    ax.set_xlabel('Relative time (s)'); ax.set_ylabel(f'ECG ({collection.unit})')
                for ax in list(axes.flat)[len(selected):]: ax.set_visible(False)
            filename=f'figures/C_morphology/{lead}_{group}_representative_grid.png'
            book.select(collection,selected,filename,'nearest centered mean + evenly spaced peak-to-peak ranks; unique samples')
            book.save(fig,'C',f'{lead}_{group}_representative_grid',f'Lead {lead} | AAMI {group} | representative and amplitude-diverse examples',
                      '选出最接近类均值的实际心拍，并补充不同峰峰值排序位置的实际片段。',
                      f'实际展示 {len(selected)} 个不同心拍；首格为减中位数后距离类均值最近的窗口，其余按峰峰值排序选取。',
                      '代表性由明确数值准则定义，不是专家诊断；极端片段可能含基线或邻拍影响；只有 2 例不能建立稳定模板。',scope)
        fig,axes=plt.subplots(1,2,figsize=(12,5),sharex=True,sharey=True)
        for ax,values,title in zip(axes,(raw,centered),('Raw window means','Window-median-centered means')):
            for group in GROUPS:
                positions=np.flatnonzero(meta.aami_group.to_numpy()==group)
                if len(positions): ax.plot(time,values[positions].mean(axis=0),c=COLORS[group],lw=1.6,label=f'{group} (n={len(positions)})')
            ax.axvline(0,c='#72777f',ls='--',lw=.7); ax.legend(fontsize=8)
            ax.set_xlabel('Time relative to original annotation (s)'); ax.set_ylabel(f'{lead} ({collection.unit})'); ax.set_title(title)
        book.save(fig,'C',f'{lead}_class_mean_comparison',f'Lead {lead} | compare class average waveforms',
                  '比较类别模板，并观察减中位数前后的基线效应。',count_text(meta),
                  '平均可能抹去少数形态或使正负偏转抵消；不同记录对模板的贡献按实际心拍数加权，不代表患者平均。',scope)
        fig,axes=plt.subplots(1,3,figsize=(13,4.8))
        descriptors=[('peak_to_peak','Peak-to-peak'),('maximum','Maximum'),('minimum','Minimum')]
        findings=[]
        for ax,(column,label) in zip(axes,descriptors):
            available=[g for g in GROUPS if (meta.aami_group==g).any()]
            values=[meta.loc[meta.aami_group==g,column].to_numpy() for g in available]
            bp=ax.boxplot(values,positions=[GROUPS.index(g)+1 for g in available],patch_artist=True,showfliers=True,flierprops={'markersize':2,'alpha':.3})
            for patch,group in zip(bp['boxes'],available): patch.set_facecolor(COLORS[group]); patch.set_alpha(.55)
            ax.set_xticks(range(1,6),[f'{g}\nn={int((meta.aami_group==g).sum())}' for g in GROUPS]); ax.set_xlabel('AAMI group')
            ax.set_ylabel(f'{label} ({collection.unit})'); ax.set_title(label)
            for group in available:
                part=meta[meta.aami_group==group]
                median=float(part[column].median()); feature_summaries.append({'lead':lead,'class':group,'feature':column,'n':len(part),'median':median,'min':float(part[column].min()),'max':float(part[column].max())})
                findings.append(f'{group}/{column} 中位数={median:.4f} {collection.unit}')
        book.save(fig,'C',f'{lead}_amplitude_boxplots',f'Lead {lead} | heartbeat-window amplitude descriptors',
                  '比较各类完整窗口的峰峰值、最大值、最小值与离群范围。','；'.join(findings),
                  '箱体为四分位区间、须为 1.5 IQR，点为须外数值，不等于医学异常；描述整个窗口而非已分割 QRS。',scope)
        fig,axes=plt.subplots(1,2,figsize=(12,4.8))
        energy_notes=[]
        for ax,column,title in zip(axes,('energy_raw','energy_centered'),('Raw window energy','Median-centered window energy')):
            all_values=meta[column].to_numpy(); positive=all_values[all_values>0]
            edges=np.geomspace(max(positive.min()*.9,1e-12),positive.max()*1.1,36) if len(positive) else np.geomspace(1e-8,1,36)
            for group in GROUPS:
                part=meta[meta.aami_group==group]
                if part.empty: continue
                ax.hist(part[column],bins=edges,histtype='step',linewidth=1.5,color=COLORS[group],label=f'{group}, n={len(part)}')
                energy_notes.append(f'{group}/{column} 中位数={part[column].median():.5f} {collection.unit}²·s')
            ax.set_xscale('log'); ax.set_yscale('symlog',linthresh=1); ax.set_title(title); ax.legend(fontsize=8)
            ax.set_xlabel(f'Sum(amplitude squared)/fs ({collection.unit}^2 s), log scale'); ax.set_ylabel('Beat count (symlog)')
        book.save(fig,'C',f'{lead}_energy_distribution',f'Lead {lead} | physical window energy distribution',
                  '比较幅值平方积分，并展示原始基线对能量的影响。','；'.join(energy_notes),
                  '能量定义为 sum(x²)/fs，不是心脏机械能或病理指标；零能量不会出现在 log 横轴，数量另见特征表。',scope)
        fig,ax=plt.subplots(figsize=(9,5))
        for group in GROUPS:
            part=meta[meta.aami_group==group]
            if len(part): ax.scatter(part.peak_to_peak,part.energy_centered,s=9,c=COLORS[group],alpha=.35,label=f'{group}, n={len(part)}')
        ax.set_xlabel(f'Window peak-to-peak ({collection.unit})'); ax.set_ylabel(f'Median-centered energy ({collection.unit}^2 s)'); ax.legend()
        book.save(fig,'C',f'{lead}_amplitude_energy_scatter',f'Lead {lead} | amplitude versus centered energy',
                  '检查幅值与能量的联合变化以及类间重叠。',
                  f'全部 {len(meta)} 个有效窗口；峰峰值与中心化能量 Pearson 相关系数={meta.peak_to_peak.corr(meta.energy_centered):.4f}。',
                  '相关性是同一窗口两个数学描述量之间的相关；不构成独立诊断证据或分类效果。',scope)
    book.tables['class_feature_summary']=pd.DataFrame(feature_summaries)
