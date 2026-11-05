"""Unsupervised projections for exploration, never a classifier evaluation."""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from threadpoolctl import threadpool_limits
from .common import COLORS, pool_scope, count_text, heatmap
from ..heartbeat import stratified_sample_indices
from ..labels import GROUPS


def projection_figure(coords,meta,xlabel,ylabel):
    fig,axes=plt.subplots(1,2,figsize=(13,5.3),sharex=True,sharey=True)
    for group in GROUPS:
        mask=meta.aami_group.to_numpy()==group
        if mask.any():
            axes[0].scatter(coords[mask,0],coords[mask,1],s=11,c=COLORS[group],alpha=.5,label=f'{group}, n={int(mask.sum())}')
    axes[0].legend(title='AAMI',fontsize=8); axes[0].set_title('Same coordinates | color = annotation group')
    names=sorted(meta.record.unique())
    palette=plt.get_cmap('turbo').resampled(max(len(names),2))
    if len(names)<=8:
        for i,name in enumerate(names):
            mask=meta.record.to_numpy()==name
            axes[1].scatter(coords[mask,0],coords[mask,1],s=11,c=[palette(i)],alpha=.45,label=f'{name}, n={int(mask.sum())}')
        axes[1].legend(title='Record',fontsize=8)
    else:
        codes=meta.record.map({n:i for i,n in enumerate(names)}).to_numpy()
        scatter=axes[1].scatter(coords[:,0],coords[:,1],c=codes,s=8,alpha=.45,cmap=palette)
        ticks=np.unique(np.linspace(0,len(names)-1,min(10,len(names)),dtype=int))
        cb=fig.colorbar(scatter,ax=axes[1],ticks=ticks,label='Record ID'); cb.ax.set_yticklabels([names[i] for i in ticks])
    axes[1].set_title('Same coordinates | color = record')
    for ax in axes: ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
    return fig


def generate(book,collections):
    coordinates,parameters,variance_rows,correlation_rows=[],[],[],[]
    for lead,collection in collections.items():
        meta=collection.metadata; centered=collection.centered; scope=pool_scope(collection)
        if len(meta)<3 or not np.any(np.var(centered,axis=0)>0):
            raise ValueError(f'{lead}: need at least 3 windows and nonconstant data for meaningful embeddings')
        rms=np.sqrt(np.mean(centered**2,axis=1,keepdims=True))
        matrices={'median_centered':centered,'median_centered_unit_rms':centered/np.where(rms>1e-12,rms,1)}
        selected=stratified_sample_indices(meta,book.config['seed'],book.config['embedding_per_stratum'],book.config['embedding_max'])
        sampled=meta.iloc[selected].reset_index(drop=True)
        selected_info=sampled[['beat_id','record','lead','annotation_index','sample','time_s','symbol','aami_group']].copy()
        selected_info['embedding_selection']='record/class capped sampling without replacement'
        book.tables[f'{lead}_embedding_sample']=selected_info
        variance_by_mode={}
        for mode,matrix in matrices.items():
            with threadpool_limits(limits=1):
                pca=PCA(svd_solver='full').fit(matrix)
                projected=pca.transform(matrix)[:,:2]
            variance_by_mode[mode]=pca.explained_variance_ratio_
            for i,value in enumerate(pca.explained_variance_ratio_):
                variance_rows.append({'lead':lead,'preprocessing':mode,'component':i+1,'explained_variance_ratio':float(value)})
            frame=meta[['beat_id','record','lead','annotation_index','sample','time_s','symbol','aami_group']].copy()
            frame['method']='PCA'; frame['preprocessing']=mode; frame['perplexity']=np.nan
            frame['axis_1']=projected[:,0]; frame['axis_2']=projected[:,1]; coordinates.append(frame)
            ratio=pca.explained_variance_ratio_[:2]*100
            fig=projection_figure(projected,meta,f'PC1 ({ratio[0]:.2f}% variance)',f'PC2 ({ratio[1]:.2f}% variance)')
            book.save(fig,'F',f'{lead}_pca_{mode}',f'Lead {lead} | PCA | {mode} | all valid windows',
                      '观察波形主要变化方向，并用相同坐标按类别和记录分别着色以检查记录效应。',
                      f'输入 {len(meta)}×{matrix.shape[1]}；PC1/PC2 解释率 {ratio[0]:.3f}%/{ratio[1]:.3f}%，合计 {ratio.sum():.3f}%；'+count_text(meta),
                      '只做无监督投影；标签仅用于着色。减窗中位数后保留原幅值，unit_rms 版本另移除每窗幅值尺度。投影分离不等于模型准确率或诊断。',scope)
            chosen=matrix[selected]
            n_components=min(50,chosen.shape[1],len(chosen)-1)
            with threadpool_limits(limits=1):
                pre_pca=PCA(n_components=n_components,svd_solver='full')
                reduced=pre_pca.fit_transform(chosen)
            for perplexity in book.config['perplexities']:
                if perplexity>=len(chosen):
                    raise ValueError(f'perplexity {perplexity} must be less than selected beats {len(chosen)}')
                print(f't-SNE: {lead}, {mode}, n={len(chosen)}, perplexity={perplexity}',flush=True)
                with threadpool_limits(limits=1):
                    tsne=TSNE(n_components=2,perplexity=perplexity,init='pca',learning_rate='auto',
                              max_iter=1000,random_state=book.config['seed'],n_jobs=1)
                    coords=tsne.fit_transform(reduced)
                frame=sampled[['beat_id','record','lead','annotation_index','sample','time_s','symbol','aami_group']].copy()
                frame['method']='t-SNE'; frame['preprocessing']=mode; frame['perplexity']=perplexity
                frame['axis_1']=coords[:,0]; frame['axis_2']=coords[:,1]; coordinates.append(frame)
                parameter={'lead':lead,'preprocessing':mode,'perplexity':perplexity,'n':len(chosen),
                           'pre_pca_components':n_components,'pre_pca_explained_variance':float(pre_pca.explained_variance_ratio_.sum()),
                           'seed':book.config['seed'],'max_iter':1000,'completed_iter':int(tsne.n_iter_),
                           'kl_divergence':float(tsne.kl_divergence_),'init':'pca','learning_rate':'auto',
                           'constant_centered_windows':int((rms[selected,0]<=1e-12).sum())}
                parameters.append(parameter)
                fig=projection_figure(coords,sampled,'t-SNE dimension 1 (arbitrary units)','t-SNE dimension 2 (arbitrary units)')
                book.save(fig,'F',f'{lead}_tsne_{mode}_p{perplexity:g}',f'Lead {lead} | t-SNE | {mode} | perplexity={perplexity:g}',
                          '检查局部形态相似性，并比较不同 perplexity 和幅值处理下的可视化稳定性。',
                          f'按记录×类别不放回抽样 {len(chosen)} 拍；{count_text(sampled)}；预 PCA={n_components} 维，保留方差 {pre_pca.explained_variance_ratio_.sum()*100:.3f}%；运行 {tsne.n_iter_} 轮，KL={tsne.kl_divergence_:.5f}。',
                          '图已受分层抽样影响，不反映原始类别频率；不同图的坐标方向/簇间距离不可直接比较，KL 不是分类性能；没有训练分类器或深度模型。',scope+f'; embedding subset={len(chosen)}; exact point IDs: results/visualization/embedding_coordinates.csv')
        fig,axes=plt.subplots(1,2,figsize=(12,4.8))
        for mode,ratios in variance_by_mode.items():
            indices=np.arange(1,min(20,len(ratios))+1)
            axes[0].plot(indices,ratios[:len(indices)]*100,marker='o',ms=3,label=mode)
            upto=min(50,len(ratios)); axes[1].plot(np.arange(1,upto+1),np.cumsum(ratios[:upto])*100,label=mode)
        axes[0].set_xlabel('Principal component'); axes[0].set_ylabel('Explained variance (%)')
        axes[1].set_xlabel('Number of components'); axes[1].set_ylabel('Cumulative explained variance (%)')
        for ax in axes: ax.legend(fontsize=7)
        book.save(fig,'F',f'{lead}_pca_explained_variance',f'Lead {lead} | PCA variance spectrum',
                  '说明二维投影丢失了多少波形变化，并比较保留幅值与单位 RMS 形态的差异。',
                  '；'.join(f'{mode}: 前 2 维 {ratios[:2].sum()*100:.3f}%，前 50 维 {ratios[:50].sum()*100:.3f}%' for mode,ratios in variance_by_mode.items()),
                  '解释率取决于预处理和当前数据分布，不能解释为分类准确率。',scope)
        templates={g:centered[meta.aami_group.to_numpy()==g].mean(axis=0) for g in GROUPS if (meta.aami_group==g).any()}
        corr=np.full((5,5),np.nan)
        for i,g in enumerate(GROUPS):
            for j,h in enumerate(GROUPS):
                if g in templates and h in templates and np.std(templates[g])>1e-12 and np.std(templates[h])>1e-12:
                    corr[i,j]=float(np.corrcoef(templates[g],templates[h])[0,1])
                correlation_rows.append({'lead':lead,'class_row':g,'class_column':h,'correlation':corr[i,j],
                                         'row_count':int((meta.aami_group==g).sum()),'column_count':int((meta.aami_group==h).sum())})
        fig,ax=plt.subplots(figsize=(8,6))
        heatmap(ax,corr,GROUPS,GROUPS,'Pearson r (class mean templates)',cmap='coolwarm',limits=(-1,1),formatter='.3f')
        ax.set_xlabel('AAMI class mean template'); ax.set_ylabel('AAMI class mean template')
        pairs=[(g,h,corr[i,j]) for i,g in enumerate(GROUPS) for j,h in enumerate(GROUPS) if i<j and np.isfinite(corr[i,j])]
        finding='；'.join(f'{g}–{h}: r={value:.4f}' for g,h,value in pairs)
        book.save(fig,'F',f'{lead}_template_correlation',f'Lead {lead} | correlation between class-average templates',
                  '比较平均波形形状的相似与反向关系，缺失或常量模板以 NA 表示。',finding,
                  '模板可能受大记录和幅值差异支配；类均值相关不代表逐拍可分性；F 极少时模板不稳定，Q 缺失不可填成 0。',scope)
    book.tables['embedding_coordinates']=pd.concat(coordinates,ignore_index=True)
    book.tables['embedding_parameters']=pd.DataFrame(parameters)
    book.tables['pca_explained_variance']=pd.DataFrame(variance_rows)
    book.tables['template_correlations']=pd.DataFrame(correlation_rows)
