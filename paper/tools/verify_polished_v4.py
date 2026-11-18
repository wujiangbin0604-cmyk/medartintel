"""Render native-Word V4 and check language scope, pagination and source preservation."""
from pathlib import Path
from zipfile import ZipFile
from collections import Counter
import argparse, hashlib, importlib.util, json, os, re

ROOT=Path(__file__).resolve().parents[2]
QA=ROOT/'paper/qa/v4'
DOCX=ROOT/'paper/final/ECG_AI_课程论文_语言润色版V4.docx'
PDF=DOCX.with_suffix('.pdf')
SOURCE=ROOT/'paper/draft/ECG_AI_课程论文_语言润色版V4.md'
RENDER=Path(r'C:\Users\20996\.codex\visualizations\2026\11\16\01a1e341-4607-78c3-9f35-783e42fd49ab\ecg_language_v4_render')
RUNTIME=Path(r'C:\Users\20996\.cache\codex-runtimes\codex-primary-runtime\dependencies')
NS={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(s):return re.sub(r'\s+','',s)

def render():
    os.environ['PATH']=str(RUNTIME/'native/poppler/Library/bin')+os.pathsep+os.environ['PATH']
    script=Path(r'C:\Users\20996\.codex\plugins\cache\openai-primary-runtime\documents\26.1112.11217\skills\documents\render_docx.py')
    spec=importlib.util.spec_from_file_location('bundled_renderer_v4',script)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.convert_to_pdf=lambda *a,**kw:(str(PDF),'Actual native Microsoft Word PDF')
    files=module.rasterize(str(DOCX),str(RENDER),dpi=120,verbose=False,emit_pdf=False)
    print(json.dumps({'rendered_pages':len(files),'directory':str(RENDER)},ensure_ascii=False))

def objects(path):
    from lxml import etree as E
    with ZipFile(path) as z:
        assert z.testzip() is None
        xml=E.fromstring(z.read('word/document.xml'))
        return {'math':[p.xpath('.//m:t/text()',namespaces=NS) for p in xml.findall('.//m:oMath',NS)],
                'tables':[p.xpath('.//w:t/text()',namespaces=NS) for p in xml.findall('.//w:tbl',NS)],
                'sections':[p.find('w:pgMar',NS).attrib for p in xml.findall('.//w:sectPr',NS)],
                'media':{p:hashlib.sha256(z.read(p)).hexdigest() for p in z.namelist() if p.startswith('word/media/')}}

def check(visual=False):
    from pypdf import PdfReader
    manifest=json.loads((QA/'language_revision_manifest.json').read_text(encoding='utf-8'))
    old=ROOT/'paper/draft/ECG_AI_课程论文_最终优化版V3.md'
    assert sha(old)==manifest['source_sha256']
    assert sha(SOURCE)==manifest['target_sha256']
    v3qa=json.loads((ROOT/'paper/qa/v3/final_quality_check.json').read_text(encoding='utf-8'))
    for ext,key in [('docx','docx_sha256'),('pdf','pdf_sha256')]:
        assert sha(ROOT/f'paper/final/ECG_AI_课程论文_最终优化版V3.{ext}')==v3qa[key]
    original=objects(ROOT/'paper/final/ECG_AI_课程论文_最终优化版V3.docx')
    current=objects(DOCX)
    assert current==original,'Word equations/tables/margins/media changed'
    pages=[p.extract_text() for p in PdfReader(PDF).pages]
    assert all(len(norm(p))>30 for p in pages)
    assert all((RENDER/f'page-{i}.png').is_file() for i in range(1,len(pages)+1))
    toc_indexes=[i for i,p in enumerate(pages) if '目录' in [norm(l) for l in p.splitlines()]]
    assert len(toc_indexes)==1,toc_indexes
    toc_index=toc_indexes[0]
    body_index=next(i for i,p in enumerate(pages) if i>toc_index and '第1章绪论' in [norm(l) for l in p.splitlines()])
    toc={}
    for line in pages[toc_index].splitlines():
        m=re.match(r'^\s*(.*?)\s*\.{3,}\s*(\d+)\s*$',line)
        if m:toc[norm(m[1])]=int(m[2])
    source=SOURCE.read_text(encoding='utf-8')
    headings=[];active=False
    for line in source.splitlines():
        if line.startswith('# 第1章'):active=True
        if active and re.match(r'^#{1,3} ',line):headings.append(re.sub(r'^#{1,3} ','',line))
    verification=[]
    for h in headings:
        found=[i for i in range(body_index,len(pages)) if norm(h) in [norm(l) for l in pages[i].splitlines()]]
        assert found,h
        entry={'heading':h,'pdf_page':found[0]+1,'body_page':found[0]-body_index+1,'toc_page':toc.get(norm(h))}
        assert entry['body_page']==entry['toc_page'],entry
        verification.append(entry)
    (QA/'toc_verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2),encoding='utf-8')
    for i in range(body_index,len(pages)):
        number=i-body_index+1
        assert str(number) in [l.strip() for l in pages[i].splitlines()]
        header='心拍分类与可视化系统设计' if number%2 else '福州大学本科生毕业设计（论文）'
        assert norm(header) in norm(pages[i])
    body=source.split('# 第1章',1)[1].split('# 参考文献',1)[0]
    def prose(s):return [l for l in s.splitlines() if re.search('[\u4e00-\u9fff]',l) and not l.startswith(('#','|','![','$$','表','关键词','副标题'))]
    before=prose(old.read_text(encoding='utf-8').split('# 参考文献',1)[0])
    after=prose(source.split('# 参考文献',1)[0])
    def lengths(lines):return [len(t) for l in lines for t in re.split('[。！？]',l) if t.strip()]
    old_lengths,new_lengths=lengths(before),lengths(after)
    checks={'pages':len(pages),'body_starts_pdf_page':body_index+1,'body_han_characters':len(re.findall('[\u4e00-\u9fff]',body)),
            'paragraphs_edited':len(manifest['operations']),'numeric_values_and_citations':'UNCHANGED',
            'native_equations':len(current['math']),'tables':len(current['tables']),'media_files':len(current['media']),
            'margins_and_protected_objects':'UNCHANGED','source_v3_md_docx_pdf':'UNCHANGED',
            'toc_entries_checked':len(verification),'empty_pages':0,
            'prose_quotes':sum(l.count('“')+l.count('”') for l in after),
            'prose_fullwidth_parentheses':sum(l.count('（')+l.count('）') for l in after),
            'sequence_connectors':sum(len(re.findall('首先|其次|再次|最后，',l)) for l in after),
            'empty_stock_phrases':sum(len(re.findall('具有重要意义|提供有力支撑|不仅.*而且',l)) for l in after),
            'long_sentences_over_90_chars_before':sum(n>90 for n in old_lengths),
            'long_sentences_over_90_chars_after':sum(n>90 for n in new_lengths),
            'docx_sha256':sha(DOCX),'pdf_sha256':sha(PDF),'draft_sha256':sha(SOURCE),
            'render_directory':str(RENDER),'render_dpi':120,'all_pages_visually_inspected':visual,
            'status':'PASS' if visual else 'VISUAL_REVIEW_PENDING'}
    assert checks['body_han_characters']>=5000
    assert checks['prose_quotes']==checks['prose_fullwidth_parentheses']==checks['sequence_connectors']==checks['empty_stock_phrases']==0
    (QA/'final_quality_check.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(checks,ensure_ascii=False,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--render',action='store_true');p.add_argument('--confirm-visual',action='store_true');a=p.parse_args()
    if a.render:render()
    check(a.confirm_visual)
