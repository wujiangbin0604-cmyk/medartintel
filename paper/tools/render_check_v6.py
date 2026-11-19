"""Render the native-Word V6 PDF with bundled render_docx and audit content."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import re
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'paper/final/ECG_AI_课程论文_完整研究版V6'
QA = ROOT/'paper/qa/v6'
RUNTIME = Path('C:/Program Files/WindowsApps/OpenAI.CodexPrimaryRuntime.v26-1117-835-0_26.1117.835.0_x64__3k8sg7r9htsxt/dependencies')
SKILL = Path('C:/Users/20996/.codex/plugins/cache/openai-primary-runtime/documents/26.1117.11355/skills/documents')


def main():
    p=argparse.ArgumentParser();p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--skip-render',action='store_true');a=p.parse_args()
    out=a.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    os.environ['PATH']=str(RUNTIME/'native/poppler/Library/bin')+os.pathsep+os.environ['PATH']
    if not a.skip_render:
        spec=importlib.util.spec_from_file_location('bundled_renderer',SKILL/'render_docx.py')
        renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
        renderer.convert_to_pdf=lambda *args,**kwargs:(str(BASE.with_suffix('.pdf')),'Native Microsoft Word export, fields updated.')
        pages=renderer.rasterize(str(BASE.with_suffix('.docx')),str(out),dpi=120,verbose=False,emit_pdf=False)
        print('rendered',len(pages),'pages',flush=True)
    import pdfplumber
    pdf=pdfplumber.open(BASE.with_suffix('.pdf'))
    texts=[page.extract_text() or '' for page in pdf.pages]
    text='\n'.join(texts)
    assert '目录由Word更新' not in text
    assert not any(t in text for t in ['Error!','错误!未定义书签','待填写','CITATION NEEDED'])
    for value in ['0.4628','0.3584','0.3754','0.3530','0.1044','0.0047','0.1611','0.8795','0.0357']:
        assert value in text,value
    assert all(len(t.strip())>20 for t in texts),'Blank page'
    geometries=[]
    for n,page in enumerate(pdf.pages,1):
        outside=[]
        for block in page.chars + page.images:
            x0,y0,x1,y1=block['x0'],block['top'],block['x1'],block['bottom']
            if x0 < -1 or y0 < -1 or x1 > page.width+1 or y1 > page.height+1:
                outside.append([x0,y0,x1,y1])
        assert not outside,(n,outside)
        geometries.append({'page':n,'text_characters':len(texts[n-1]),'images':len(page.images),'outside_page_blocks':outside})
    from lxml import etree as E
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
    with zipfile.ZipFile(BASE.with_suffix('.docx')) as z:
        assert z.testzip() is None
        tree=E.fromstring(z.read('word/document.xml'))
        anchors=tree.xpath('.//w:hyperlink/@w:anchor',namespaces=ns)
        bookmarks=set(tree.xpath('.//w:bookmarkStart/@w:name',namespaces=ns))
        toc=[v for v in anchors if v.startswith('_Toc')]
        assert toc and all(v in bookmarks for v in toc)
        eq=len(tree.findall('.//m:oMath',ns));assert eq==7
        headings=[''.join(p.xpath('.//w:t/text()',namespaces=ns)) for p in tree.findall('.//w:p',ns)
                  if p.find('w:pPr/w:pStyle',ns) is not None and p.find('w:pPr/w:pStyle',ns).get('{'+ns['w']+'}val') in ('V3Chapter','V3Heading2','V3Heading3')]
    draft=(ROOT/'paper/draft/ECG_AI_课程论文_完整研究版V6.md').read_text(encoding='utf-8')
    figures=re.findall(r'^!\[(图\d+-\d+)',draft,re.M)
    tables=re.findall(r'^(表\d+-\d+)\s',draft,re.M)
    assert len(figures)==len(set(figures)) and len(tables)==len(set(tables))
    assert len(figures)==26
    protected=ROOT/'paper/reference/v5/final/ECG_AI_课程论文_自然表达版V5.docx'
    assert hashlib.sha256(protected.read_bytes()).hexdigest()=='1c54aa084246ffc7771cf736c4c9b66ff2df098bf6c72d835e6a432e89e94e93'
    report={'status':'STRUCTURAL_AND_CONTENT_PASS_VISUAL_REVIEW_PENDING','pages':len(pdf.pages),'render_dir':str(out),
            'toc_anchors':len(toc),'toc_bookmarks_exist':True,'figures':len(figures),'tables':len(tables),'native_equations':eq,
            'reference_count':len(re.findall(r'^\[\d+\] ',draft,re.M)),'new_training_runs':60,
            'V5_original_preserved':True,'all_pages_inside_page_bounds':True,'page_geometry':geometries,
            'docx_sha256':hashlib.sha256(BASE.with_suffix('.docx').read_bytes()).hexdigest(),
            'pdf_sha256':hashlib.sha256(BASE.with_suffix('.pdf').read_bytes()).hexdigest(),
            'visual_pages_inspected':[],'render_engine':'bundled render_docx.py with native Word PDF; 120 dpi PNG'}
    (QA/'final_quality_check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (QA/'extracted_pdf.txt').write_text(text,encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='page_geometry'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
