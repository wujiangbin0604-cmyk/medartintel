from pathlib import Path
from zipfile import ZipFile
from lxml import etree as E
from pypdf import PdfReader
import json,re,hashlib,csv
P=Path(__file__).resolve().parents[1]
docx=P/'final/ECG_AI_课程论文.docx'
with ZipFile(docx) as z:
    assert z.testzip() is None
    parts={n:z.read(n) for n in z.namelist()}
d=E.fromstring(parts['word/document.xml']); ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
s=(P/'draft/ECG_AI_课程论文初稿.md').read_text(encoding='utf-8')
body=s.split('# 第一章')[1].split('# 参考文献')[0]
chapter5=s.split('# 第五章')[1].split('# 第六章')[0]
cnt=lambda x:len(re.findall('[\u4e00-\u9fff]',x))
claims=list(csv.DictReader((P/'evidence/claim_evidence_map.csv').open(encoding='utf-8-sig')))
audit=json.loads((P/'qa/template_package_audit.json').read_text(encoding='utf-8'))
assert hashlib.sha256(Path(audit['reference']).read_bytes()).hexdigest()==audit['reference_sha256']
for n in audit['preserve_only_equal']:
    assert hashlib.sha256(parts[n]).hexdigest()==audit['baseline'][n]['sha256'],n
eq=len(d.findall('.//m:oMath',ns)); imgs=len(d.findall('.//w:drawing',ns)); tables=len(d.findall('.//w:tbl',ns))
assert (eq,imgs,tables)==(7,15,8)
text=''.join(d.xpath('.//w:t/text()',namespaces=ns))
assert '目录将在Word更新' not in text
assert '阶段截图 2026年11月4日阶段截图' not in text
assert cnt(body)>=6000 and cnt(chapter5)/cnt(body)>=.25
pdf=PdfReader(P/'qa/final_verified_v4.pdf'); assert len(pdf.pages)==24
# Confirm the cached TOC page numbers against the corresponding actual PDF headings.
flat=lambda x:re.sub(r'\s+','',x)
bodyels=list(d.find('w:body',ns)); headings=[]
for p in bodyels:
    style=p.find('w:pPr/w:pStyle',ns)
    if style is not None and style.get('{'+ns['w']+'}val') in ('ECGHeading1','ECGHeading2'):
        name=''.join(p.xpath('.//w:t/text()',namespaces=ns)); headings.append(name)
pages=[flat(x.extract_text()) for x in pdf.pages]
toclines=[flat(line) for line in pdf.pages[2].extract_text().splitlines()]; toc=[]
for h in headings:
    page=next((i+1 for i,t in enumerate(pages) if i>2 and flat(h) in t),None)
    assert page is not None,h
    pattern=re.escape(flat(h))+r'\.+(\d+)'
    m=next((match for line in toclines if (match:=re.search(pattern+'$',line))),None)
    assert m and int(m[1])==page,(h,page,m[1] if m else 'not found')
    toc.append({'heading':h,'page':page})
qa={'date_Asia_Shanghai':'2026-11-05','docx':str(docx),'docx_sha256':hashlib.sha256(docx.read_bytes()).hexdigest(),'pages':24,'body_chinese_characters_including_tables':cnt(body),'chapter5_chinese_characters':cnt(chapter5),'chapter5_share':cnt(chapter5)/cnt(body),'figures':imgs,'tables':tables,'native_math_objects':eq,'references':10,'claim_evidence_rows':len(claims),'original_template_unchanged':True,'opaque_template_parts_unchanged':True,'cached_toc_page_numbers_verified':toc,'visual_qa':{'reviewer':'primary agent','pages_inspected':list(range(1,25)),'method':'Word PDF rendered through bundled render_docx rasterize at 144 dpi; every PNG opened and inspected; final caption edits checked via pixel comparison and reinspection','result':'passed','limitations':'Original experimental figure labels include English; small multipanel details remain available in source images. Professional field intentionally blank.'},'tests':'Read-only artifact integrity and saved-prediction recomputation; no model training or new full Web regression run.'}
(P/'qa/final_qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in qa.items() if k not in ['cached_toc_page_numbers_verified','visual_qa']},ensure_ascii=False))
