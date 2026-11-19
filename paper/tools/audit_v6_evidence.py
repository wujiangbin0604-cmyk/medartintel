"""Check new paper tables against frozen machine-readable results."""
from pathlib import Path
import json
import statistics
import re

ROOT=Path(__file__).resolve().parents[2]


def main():
    text=(ROOT/'paper/draft/ECG_AI_课程论文_完整研究版V6.md').read_text(encoding='utf-8')
    s=json.loads((ROOT/'research_extensions/rhythm_fusion/results/cv_cpu_v1/summary.json').read_text())
    u=json.loads((ROOT/'research_extensions/uncertainty/results/cv_cpu_v1/summary.json').read_text())
    checks=[]
    def table(number):
        part=re.search(r'^表'+number+r' .*?\n\n((?:\|.*\n)+)',text,re.M)[1]
        return [[v.strip() for v in line.strip('|').split('|')] for line in part.splitlines()[2:]]
    def near(actual,expected,where):
        assert abs(float(actual)-expected)<=0.000051,(where,actual,expected)
        checks.append(where)
    for row in table('5-9'):
        models=[r for r in s['models'] if r['model']==row[0]]; assert len(models)==3
        for col,key in [(1,'macro_f1'),(2,'accuracy'),(3,'balanced_accuracy')]:
            v=[r['pooled'][key] for r in models];m,sd=row[col].split(' ± ')
            near(m,statistics.mean(v),row[0]+key+'mean')
            near(sd,statistics.stdev(v),row[0]+key+'sd')
        assert int(row[4])==models[0]['parameters']
    for row in table('5-10'):
        values={r['model']:r['pooled']['macro_f1'] for r in s['models'] if r['seed']==int(row[0])}
        for col,model in enumerate(['A0','A1','A2','A3'],1):near(row[col],values[model],row[0]+model)
        near(row[5],values['A2']-values['A0'],row[0]+'delta')
    for row in table('5-11'):
        model,label=row[0].split('/')
        values=[r['pooled']['per_class'][label] for r in s['models'] if r['model']==model]
        for col,key in enumerate(['precision','recall','f1'],1):
            near(row[col],statistics.mean(r[key] for r in values),row[0]+key)
        n,p=map(int,row[4].split('/'));assert n==values[0]['support'] and p==values[0]['subject_count']
    for row in table('5-12'):
        model,method=row[0].split('/');method='max_score' if method=='最大分数' else 'entropy'
        values=[r for r in u['results'] if r['model']==model and r['method']==method];assert len(values)==3
        for col,key in enumerate(['coverage','all_error_rate','accepted_error_rate','rejected_error_rate','error_detection_auroc'],1):
            # Historical result schema uses error_auroc for the same quantity.
            if key not in values[0] and key=='error_detection_auroc':key='error_auroc'
            near(row[col],statistics.mean(r[key] for r in values),row[0]+key)
    for row in table('5-13'):
        method,label=row[0].split('/');method='max_score' if method=='最大分数' else 'entropy'
        values=[r['per_class'][label] for r in u['results'] if r['model']=='A2' and r['method']==method]
        for col,key in enumerate(['acceptance_rate','precision_retained','recall_retained_denominator','recall_all_denominator'],1):
            near(row[col],statistics.mean(r[key] for r in values),row[0]+key)
    assert len(s['folds'])==60 and len(u['thresholds'])==120 and len(u['results'])==24
    assert s['sample_count']==86286 and s['subject_count']==37
    result={'status':'PASS','numeric_comparisons':len(checks),'checked_tables':['5-9','5-10','5-11','5-12','5-13'],
            'completed_training_jobs':60,'thresholds':120,'uncertainty_results':24,'independent_patients':37,'beats':86286}
    (ROOT/'paper/qa/v6/evidence_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
