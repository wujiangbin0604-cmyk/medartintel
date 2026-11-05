"""Restore native color display of the existing cover logo and edit its title."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
import hashlib,json,shutil

P=Path(__file__).resolve().parents[1]
target=P/'final/ECG_AI_课程论文.docx'
backup=P/'qa/before_colored_title.docx'
if not backup.exists(): shutil.copy2(target,backup)
with ZipFile(target) as z: parts={n:z.read(n) for n in z.namelist()}
old=dict(parts)
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','v':'urn:schemas-microsoft-com:vml'}
tree=E.fromstring(parts['word/document.xml']); body=tree.find('w:body',ns)
previous=[E.tostring(e) for e in body]
assert len(body[1].findall('.//v:imagedata',ns))==4
for image in body[1].findall('.//v:imagedata',ns):
    image.attrib.pop('grayscale',None)
    image.attrib.pop('bilevel',None)
nodes=body[3].findall('.//w:t',ns)
assert nodes
nodes[0].text='医学人工智能课程项目论文'
for t in nodes[1:]: t.text=''
for i,e in enumerate(body):
    if i not in (1,3): assert E.tostring(e)==previous[i],i
parts['word/document.xml']=E.tostring(tree,encoding='UTF-8',xml_declaration=True,standalone=True)
with ZipFile(target,'w',ZIP_DEFLATED) as z:
    for name,content in parts.items(): z.writestr(name,content)
changed=[n for n in parts if parts[n]!=old[n]]
assert changed==['word/document.xml'],changed
audit={'title':'医学人工智能课程项目论文','native_logo_color_restored':True,'logo_bitmaps_and_OLE_unchanged':True,'only_changed_cover_paragraphs':[1,3],'remaining_cover_and_body_xml_unchanged':True,'changed_package_parts':changed,'docx_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
(P/'qa/colored_title_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False))
