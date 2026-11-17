"""Format the revised manuscript with the existing school cover and native math."""
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
import re,json
P=Path(__file__).resolve().parents[1]
code=(P/'tools/build_paper.py').read_text(encoding='utf-8')
code=code.replace("PAPER/'qa/body.docx'","PAPER/'qa/v2/body.docx'")
code=code.replace("PAPER/'final/ECG_AI_课程论文.docx'","PAPER/'final/ECG_AI_课程论文_修订版V2.docx'")
code=code.replace("PAPER/'qa/template_package_audit.json'","PAPER/'qa/v2/template_package_audit.json'")
code=code.replace("('ECGHeading2',14,'黑体',True)","('ECGHeading2',14,'黑体',True),('ECGHeading3',12,'黑体',True)")
code=code.replace("if line.startswith('## '):","if line.startswith('### '):\n            p=d.add_paragraph(line[4:],'ECGHeading3'); continue\n        if line.startswith('## '):")
code=code.replace("'0' if name.endswith('1') else '1'","'0' if name.endswith('1') else '1' if name.endswith('2') else '2'")
code=code.replace("im=Image.open(path); width=6.1;", "im=Image.open(path); width=3.8 if path.name=='system_comparison_cards.png' else 6.1;")
code=code.replace("p=d.add_paragraph(style='ECGFigure'); p.add_run().add_picture(str(path),width=Inches(width))", "p=d.add_paragraph(style='ECGFigure'); p.add_run().add_picture(str(path),width=Inches(width))\n            if p._p.getprevious() is not None and p._p.getprevious().tag==qn('w:tbl'): p.paragraph_format.space_before=Pt(6)")
code=code.replace("if rownum<len(cells)-1: p.paragraph_format.keep_with_next=True","if rownum==0 or (len(cells)<=6 and rownum<len(cells)-1): p.paragraph_format.keep_with_next=True")
code=code.replace("p=d.add_paragraph(line,'ECGReference' if refmode else 'ECGBody')", "p=d.add_paragraph(line,'ECGReference' if refmode else 'ECGBody')\n        if p._p.getprevious() is not None and p._p.getprevious().tag==qn('w:tbl'): p.paragraph_format.space_before=Pt(7)")
g={'__name__':'v2_builder','__file__':str(P/'tools/build_paper.py')};exec(compile(code,str(P/'tools/build_v2_docx.py'),'exec'),g)
s=(P/'draft/ECG_AI_课程论文_修订版V2.md').read_text(encoding='utf-8')
g['body_doc'](s); output=g['merge_package']()
with ZipFile(output) as z: parts={n:z.read(n) for n in z.namelist()}
W=g['W'];ns=g['NS'];qn=g['qn']; tree=E.fromstring(parts['word/document.xml']);ps=tree.find('w:body',ns).findall('w:p',ns)
for idx,value in [(7,'吴江彬'),(9,'102400329'),(11,'计算机与大数据学院'),(13,'待填写'),(15,'2024级'),(17,'胡桓')]:
    ts=ps[idx].findall('.//w:t',ns);blank=[t for t in ts if not (t.text or '').strip()];total=sum(len(t.text or '') for t in blank)
    blank[0].text=value+' '*max(2,total-sum(2 if ord(c)>127 else 1 for c in value))
    for t in blank[1:]:t.text=''
t=ps[5].findall('.//w:t',ns)[-1];t.text='基于一维卷积神经网络的心电图'
t.getparent().find('w:rPr/w:sz',ns).set(qn('w:val'),'28')
g['cover_replace'](ps[6],'异常心拍识别与可视化系统设计',28)
ind=ps[6].find('w:pPr/w:ind',ns);ind.set(qn('w:left'),'2255');ind.set(qn('w:firstLine'),'0')
g['cover_replace'](ps[19],'2026年11月6日')
parts['word/document.xml']=g['dump'](tree)
with ZipFile(output,'w',ZIP_DEFLATED) as z:
    for n,b in parts.items():z.writestr(n,b)
print(output)
