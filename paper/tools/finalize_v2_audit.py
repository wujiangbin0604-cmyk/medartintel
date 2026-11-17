"""Integrity, source-data, numbering and cached-directory checks for V2."""
from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from pypdf import PdfReader
from collections import Counter
import hashlib,json,csv,re,difflib
P=Path(__file__).resolve().parents[1];ROOT=P.parent
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def readcsv(p):return list(csv.DictReader(p.open(encoding='utf-8-sig')))
for rel in ['final/ECG_AI_课程论文.docx','draft/ECG_AI_课程论文初稿.md']:
    assert digest(P/rel)==digest(P/'review/backup_v1'/Path(rel).name),'V1 changed'
j=json.loads((P/'evidence/verified_metrics.json').read_text(encoding='utf-8'))
unchanged=[]
for rel,val in j['source_inventory'].items():
    assert digest(ROOT/rel)==val['sha256'],rel
    unchanged.append(rel)
recomputed=[]
for task,models in j['test_metrics'].items():
    classes=['N','V'] if task=='nv' else ['N','S','V','F']
    for name,expected in models.items():
        rows=readcsv(ROOT/expected['prediction_source']); cm=Counter((r['true_aami_label'],r['predicted_aami_label']) for r in rows);f1=[]
        for c in classes:
            tp=cm[c,c];support=sum(cm[c,p] for p in classes);pc=sum(cm[t,c] for t in classes);f1.append(2*tp/(support+pc) if support+pc else 0)
        acc=sum(cm[c,c] for c in classes)/len(rows);macro=sum(f1)/len(f1)
        assert abs(acc-expected['accuracy'])<1e-12 and abs(macro-expected['macro_f1'])<1e-12
        recomputed.append({'task':task,'model':name,'accuracy':acc,'macro_f1':macro})
numbers=json.loads((P/'qa/v2/numbering.json').read_text(encoding='utf-8'))
cols=['论文位置','结论文本','指标或数据','来源文件','表格或图像路径','是否核验','备注','修改说明']
claims=readcsv(P/'review/backup_v1/claim_evidence_map.csv')
for r in claims:
    for kind,key in [('图','figures'),('表','tables')]:
        r['表格或图像路径']=re.sub(kind+r'(\d+)',lambda m:kind+str(numbers[key].get('old'+m[1],int(m[1]))),r['表格或图像路径'])
    r['修改说明']='V2保留原实验结论；图表编号依正文更新'
for file in ['claim_evidence_v2_nv.csv','claim_evidence_v2_system.csv']:
    for r in readcsv(P/'evidence'/file):
        r['修改说明']='V2新增回顾性统计或系统证据；不改变正式实验工件';claims.append(r)
with (P/'evidence/claim_evidence_map.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=cols);w.writeheader();w.writerows({k:r.get(k,'') for k in cols} for r in claims)
doc=P/'final/ECG_AI_课程论文_修订版V2.docx'
with ZipFile(doc) as z:
    assert z.testzip() is None;parts={n:z.read(n) for n in z.namelist()}
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
d=E.fromstring(parts['word/document.xml']);pdf=PdfReader(P/'qa/v2/final_axis_verified.pdf' if (P/'qa/v2/final_axis_verified.pdf').exists() else P/'qa/v2/final_verified.pdf')
assert len(d.findall('.//m:oMath',ns))==7
assert len(d.findall('.//w:drawing',ns))==16
assert len(d.findall('.//w:tbl',ns))==15
full=''.join(d.xpath('.//w:t/text()',namespaces=ns));assert '目录将在Word更新' not in full
assert '2026年11月6日' in full and '医学人工智能课程项目论文' in full
assert '143' in full and '2477' in full and '5.7' in full
s=(P/'draft/ECG_AI_课程论文_修订版V2.md').read_text(encoding='utf-8')
figs=list(re.finditer(r'!\[(图(\d+) .+?)\]\((.+)\)',s))
assert [int(m[2]) for m in figs]==list(range(1,17))
assert [int(x) for x in re.findall(r'^表(\d+)\s',s,re.M)]==list(range(1,16))
for m in figs:assert (P/'draft'/m[3]).resolve().is_file()
flat=lambda s:re.sub(r'\s+','',s)
pdftexts=[flat(page.extract_text()) for page in pdf.pages];toclines=[flat(x) for x in pdf.pages[2].extract_text().splitlines()]
toc=[]
for p in d.find('w:body',ns):
    st=p.find('w:pPr/w:pStyle',ns)
    if st is None or st.get('{'+ns['w']+'}val') not in ('ECGHeading1','ECGHeading2'):continue
    name=''.join(p.xpath('.//w:t/text()',namespaces=ns))
    page=next(i+1 for i,t in enumerate(pdftexts) if i>2 and flat(name) in t)
    m=next((v for line in toclines if (v:=re.search(re.escape(flat(name))+r'\.+(\d+)$',line))),None)
    assert m and int(m[1])==page,(name,page,m[1] if m else None)
    toc.append({'heading':name,'page':page})
base=(P/'review/backup_v1/ECG_AI_课程论文初稿.md').read_text(encoding='utf-8')
(P/'review/v1_v2_text.diff').write_text(''.join(difflib.unified_diff(base.splitlines(True),s.splitlines(True),fromfile='V1',tofile='V2')),encoding='utf-8')
qa={'date':'2026-11-06','pages':len(pdf.pages),'figures':16,'tables':15,'editable_math':7,'references':10,'claim_rows':len(claims),'original_word_and_markdown_unchanged':True,'protected_experiment_files_unchanged':len(unchanged),'formal_metrics_recomputed':recomputed,'toc_verified':toc,'docx_sha256':digest(doc),'visual_qa':'See review/figure_quality_report.md and per-page visual audit','submission_date':'2026年11月6日 user-confirmed','unfilled_personal_information':['专业']}
(P/'qa/v2/final_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in qa.items() if k not in ['toc_verified','formal_metrics_recomputed']},ensure_ascii=False))
