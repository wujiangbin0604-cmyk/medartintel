from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
import re
P=Path(__file__).resolve().parents[1]
def fix(s): return re.sub(r'( 2026年11月4日阶段截图){2,}', ' 2026年11月4日阶段截图', s)
for name in ['draft/ECG_AI_课程论文初稿.md','figures/figure_index.md']:
    p=P/name; p.write_text(fix(p.read_text(encoding='utf-8')),encoding='utf-8')
p=P/'final/ECG_AI_课程论文.docx'
with ZipFile(p) as z: parts={n:z.read(n) for n in z.namelist()}
t=E.fromstring(parts['word/document.xml']); count=0
for node in t.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'):
    if node.text and fix(node.text)!=node.text: node.text=fix(node.text); count+=1
assert count==3,count
parts['word/document.xml']=E.tostring(t,encoding='UTF-8',xml_declaration=True,standalone=True)
with ZipFile(p,'w',ZIP_DEFLATED) as z:
    for n,b in parts.items(): z.writestr(n,b)
print('Removed duplicate stage dates from 3 captions; no other document parts changed.')
