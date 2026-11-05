"""A–F visualization atlas: python -m src.visualize --records 100 200 --offline."""
import argparse
from collections import Counter
from datetime import datetime
from importlib.metadata import version
import json
from pathlib import Path
import platform
import re
from zoneinfo import ZoneInfo
import numpy as np
import pandas as pd
from PIL import Image
import wfdb
from .download import prepare_data,sha256
from .io import load_record
from .analysis import summarize_labels,signal_quality
from .heartbeat import extract_heartbeats
from .visuals.common import FigureBook,FAMILIES
from .visuals import distribution,waveforms,morphology,rhythm,quality,embedding
from .visualization_report import generate_report


def write_json(value,path):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')


def verify_outputs(root,book,records,beats,collections,annotations,manifest,tables):
    expected=Counter(s for record in records for s in wfdb.rdann(str(root/'data/mitdb'/record.name),'atr').symbol)
    actual=pd.read_csv(root/'results/visualization/raw_symbol_counts.csv',keep_default_na=False)
    if expected!=dict(zip(actual.symbol,actual['count'].astype(int))): raise AssertionError('Raw symbol counts mismatch')
    if sum(expected.values())!=len(annotations): raise AssertionError('Total annotation count mismatch')
    seen=set()
    for item in book.entries:
        if item['file'] in seen: raise AssertionError('Duplicate figure filename')
        seen.add(item['file'])
        path=root/item['file']
        if path.parts[-2]!=FAMILIES[item['category']]: raise AssertionError('Incorrect category directory')
        with Image.open(path) as image:
            if image.width<700 or image.height<700: raise AssertionError('Figure too small')
            if not np.allclose(image.info.get('dpi',(0,0)),(300,300),atol=1): raise AssertionError('PNG DPI mismatch')
            image.verify()
    record_map={r.name:r for r in records}
    for collection in collections.values():
        for i,row in collection.metadata.iterrows():
            record=record_map[row.record]; channel=record.leads.index(row.lead)
            start,stop,sample=int(row.window_start_sample),int(row.window_stop_sample_exclusive),int(row['sample'])
            if not 0<=start<=sample<stop<=len(record.signal): raise AssertionError('Window out of range')
            if not np.array_equal(collection.raw[i],record.signal[start:stop,channel]): raise AssertionError('Original window content mismatch')
    selections=tables['plotted_heartbeat_windows']
    if selections.duplicated(['figure_file','beat_id']).any(): raise AssertionError('A sampled figure repeats a heartbeat')
    coordinates=tables['embedding_coordinates']
    if not np.isfinite(coordinates[['axis_1','axis_2']].to_numpy()).all(): raise AssertionError('Nonfinite embedding')
    valid_ids=set(tables['heartbeat_features'].beat_id)
    if not set(coordinates.beat_id).issubset(valid_ids): raise AssertionError('Untraceable embedded heartbeat')
    for lead in collections:
        sampled=tables[f'{lead}_embedding_sample']
        if not sampled.beat_id.is_unique: raise AssertionError('Embedding sample duplicates')
    for item in manifest:
        if sha256(root/'data/mitdb'/item['file'])!=item['sha256']: raise AssertionError('Raw file was modified')
    report=root/'reports/visualization_summary.md'
    text=report.read_text(encoding='utf-8')
    for link in re.findall(r'\]\(([^)]+)\)',text):
        if not link.startswith('http') and not (report.parent/link).is_file(): raise AssertionError(f'Broken report link: {link}')
    if any(text.count(f"#### {entry['figure_id']} ·")!=1 for entry in book.entries): raise AssertionError('Figure report coverage mismatch')
    return {'passed':True,'records':[r.name for r in records],
            'png_count':len(book.entries),'png_by_category':{c:sum(e['category']==c for e in book.entries) for c in FAMILIES},
            'png_integrity_and_300dpi':True,'all_figures_explained_in_report':True,
            'csv_count':len(tables),'total_annotations':len(annotations),
            'mapped_beats':int(tables['aami_counts']['count'].sum()),
            'valid_heartbeat_windows':sum(len(c.raw) for c in collections.values()),
            'excluded_windows':int((beats.extraction_status!='valid').sum()),
            'raw_symbol_counts_match_wfdb':True,'window_samples_match_original_signal':True,
            'random_samples_without_replacement':True,'all_embedding_points_traceable':True,
            'raw_file_hashes_unchanged':True,'trained_classifier_or_deep_model':False,'dataset_split':None}


def main():
    parser=argparse.ArgumentParser(description='Generate the MIT-BIH A–F visualization atlas, without classifier training')
    parser.add_argument('--records',nargs='+',default=['100','200'])
    parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--offline',action='store_true')
    parser.add_argument('--seed',type=int,default=20261027)
    parser.add_argument('--pre-s',type=float,default=.25)
    parser.add_argument('--post-s',type=float,default=.45)
    parser.add_argument('--embedding-per-stratum',type=int,default=500)
    parser.add_argument('--embedding-max',type=int,default=3000)
    parser.add_argument('--perplexities',nargs='+',type=float,default=[15.,40.])
    args=parser.parse_args()
    if not np.isfinite([args.pre_s,args.post_s,*args.perplexities]).all() or min(args.pre_s,args.post_s,*args.perplexities)<=0:
        parser.error('Window lengths and perplexities must be finite and positive')
    if args.seed<0 or args.embedding_per_stratum<1 or args.embedding_max<3:
        parser.error('Require seed >= 0, positive per-stratum cap, embedding maximum >= 3')
    root=args.root.resolve(); output=root/'results/visualization'
    output.mkdir(parents=True,exist_ok=True); (root/'reports').mkdir(parents=True,exist_ok=True)
    write_json({'passed':False,'status':'running_or_incomplete'},output/'verification.json')
    names,manifest=prepare_data(root/'data/mitdb',args.records,args.offline)
    records,metadata,summaries=[],[],[]
    for name in names:
        record,checks=load_record(root/'data/mitdb',name)
        if set(record.units)!={'mV'}: raise ValueError(f'{name}: expected mV units; explicit conversion is required before pooling')
        records.append(record); metadata.append(checks); summaries.append(signal_quality(record)[0])
    annotations=pd.concat([r.annotations for r in records],ignore_index=True)
    beats,collections=extract_heartbeats(records,args.pre_s,args.post_s)
    if not collections: raise ValueError('No complete, finite, mapped heartbeat windows are available')
    config={'records':names,'database_version':'1.0.0','root':str(root),'seed':args.seed,
            'pre_s':args.pre_s,'post_s':args.post_s,'embedding_per_stratum':args.embedding_per_stratum,
            'embedding_max':args.embedding_max,'perplexities':list(dict.fromkeys(args.perplexities)),
            'offline':args.offline,'dpi':300,'generated_at_Asia_Shanghai':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
            'trained_classifier_or_deep_model':False,'dataset_split':None}
    book=FigureBook(root,records,config)
    label_tables=summarize_labels(annotations,names)
    summary=pd.concat(summaries,ignore_index=True)
    book.tables.update({**label_tables,'record_metadata':pd.DataFrame(metadata),'download_manifest':pd.DataFrame(manifest),
                        'all_beat_metadata':beats,'heartbeat_features':pd.concat([c.metadata for c in collections.values()],ignore_index=True),
                        'signal_quality':summary})
    distribution.generate(book,annotations,label_tables)
    waveforms.generate(book,collections)
    morphology.generate(book,collections)
    rhythm.generate(book,beats)
    quality.generate(book,beats,summary)
    embedding.generate(book,collections)
    tables=book.write_tables()
    write_json(config,output/'run_config.json')
    write_json({'python':platform.python_version(),'platform':platform.platform(),
                **{m:version(m) for m in ('wfdb','numpy','pandas','matplotlib','scikit-learn')}},output/'environment.json')
    generate_report(root,book,annotations,beats,tables,config,manifest)
    verification=verify_outputs(root,book,records,beats,collections,annotations,manifest,tables)
    write_json(verification,output/'verification.json')
    print(json.dumps(verification,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
