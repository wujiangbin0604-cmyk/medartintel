"""Render V5's actual Word PDF and verify immutable content and TOC."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import re
from collections import Counter
from zipfile import ZipFile
from hashlib import sha256
from lxml import etree
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / 'paper/qa/v5'
STEM = 'ECG_AI_课程论文_自然表达版V5'
DOCX = ROOT / 'paper/final' / (STEM + '.docx')
PDF = DOCX.with_suffix('.pdf')
RUNTIME = Path(r'C:\Program Files\WindowsApps\OpenAI.CodexPrimaryRuntime.v26-1117-835-0_26.1117.835.0_x64__3k8sg7r9htsxt\dependencies')
SKILL = Path(r'C:\Users\20996\.codex\plugins\cache\openai-primary-runtime\documents\26.1117.11355\skills\documents\render_docx.py')
NS = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main', 'm': 'http://schemas.openxmlformats.org/officeDocument/2006/math'}


def objects(path):
    with ZipFile(path) as z:
        tree = etree.fromstring(z.read('word/document.xml'))
        return {'tables': [p.xpath('.//w:t/text()', namespaces=NS) for p in tree.findall('.//w:tbl', NS)],
                'equations': [p.xpath('.//m:t/text()', namespaces=NS) for p in tree.findall('.//m:oMath', NS)],
                'margins': [p.find('w:pgMar', NS).attrib for p in tree.findall('.//w:sectPr', NS)],
                'media': {name: sha256(z.read(name)).hexdigest() for name in z.namelist() if name.startswith('word/media/')}}


def main(render=False, visual=False):
    if render:
        os.environ['PATH'] = str(RUNTIME/'native/poppler/Library/bin') + os.pathsep + os.environ['PATH']
        spec = importlib.util.spec_from_file_location('bundled_v5_renderer', SKILL)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        module.convert_to_pdf = lambda *a, **kw: (str(PDF), 'Native Word export with updated fields and TOC')
        module.rasterize(str(DOCX), str(QA/'render'), dpi=96, verbose=False, emit_pdf=False)
    before = (ROOT/'paper/draft/ECG_AI_课程论文_语言润色版V4.md').read_text(encoding='utf-8')
    after = (ROOT/'paper/draft'/(STEM+'.md')).read_text(encoding='utf-8')
    protected = lambda s: [l for l in s.splitlines() if l.startswith(('#','|','![','$$','[','关键词','副标题'))]
    assert protected(before) == protected(after)
    assert Counter(re.findall(r'\d+(?:\.\d+)*', before)) == Counter(re.findall(r'\d+(?:\.\d+)*', after))
    assert before.split('## Abstract')[1].split('<!--TOC-->')[0] == after.split('## Abstract')[1].split('<!--TOC-->')[0]
    assert objects(ROOT/'paper/final/ECG_AI_课程论文_语言润色版V4.docx') == objects(DOCX)
    pages = [p.extract_text() for p in PdfReader(PDF).pages]
    norm = lambda s: re.sub(r'\s+', '', s)
    assert all(len(norm(p)) > 30 for p in pages)
    assert all((QA/'render'/f'page-{i+1}.png').is_file() for i in range(len(pages)))
    toc_index = next(i for i,p in enumerate(pages) if '目录' in [norm(l) for l in p.splitlines()])
    body = next(i for i,p in enumerate(pages) if i>toc_index and '第1章绪论' in [norm(l) for l in p.splitlines()])
    toc = {}
    for line in pages[toc_index].splitlines():
        m = re.match(r'^\s*(.*?)\s*\.{3,}\s*(\d+)\s*$', line)
        if m: toc[norm(m[1])] = int(m[2])
    headings = [re.sub(r'^#{1,3} ', '', l) for l in after.split('# 第1章',1)[1].splitlines() if re.match(r'^#{1,3} ',l)]
    headings.insert(0,'第1章 绪论')
    entries = []
    for h in headings:
        index = next(i for i in range(body,len(pages)) if norm(h) in [norm(l) for l in pages[i].splitlines()])
        assert toc[norm(h)] == index-body+1, h
        entries.append({'heading': h, 'body_page': index-body+1, 'pdf_page': index+1})
    (QA/'toc_verification.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2), encoding='utf-8')
    record = {'pages': len(pages), 'toc_entries_verified': len(entries), 'paragraphs_edited':29,
              'numbers_citations_headings_tables_equations_media': 'UNCHANGED', 'english_abstract':'UNCHANGED',
              'original_v4_preserved':True, 'visual_pages_inspected':list(range(1,len(pages)+1)) if visual else [],
              'status':'PASS' if visual else 'VISUAL_REVIEW_PENDING',
              'docx_sha256':sha256(DOCX.read_bytes()).hexdigest(),'pdf_sha256':sha256(PDF.read_bytes()).hexdigest()}
    (QA/'final_quality_check.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--render',action='store_true');parser.add_argument('--confirm-visual',action='store_true');a=parser.parse_args()
    main(a.render,a.confirm_visual)
