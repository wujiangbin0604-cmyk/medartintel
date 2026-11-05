"""Copy the user's original title page verbatim into the completed paper."""
from pathlib import Path
from copy import deepcopy
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
import hashlib,json,shutil

P=Path(__file__).resolve().parents[1]
reference=Path(r'C:\Users\20996\Downloads\报告title.docx')
target=P/'final/ECG_AI_课程论文.docx'
backup=P/'qa/before_original_title_restore.docx'
if not backup.exists(): shutil.copy2(target,backup)
def digest(b): return hashlib.sha256(b).hexdigest()
reference_hash=digest(reference.read_bytes())
with ZipFile(reference) as z: source={n:z.read(n) for n in z.namelist()}
with ZipFile(target) as z: parts={n:z.read(n) for n in z.namelist()}
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
ns={'w':W}
src=E.fromstring(source['word/document.xml'])
dst=E.fromstring(parts['word/document.xml'])
sb=src.find('w:body',ns); db=dst.find('w:body',ns)
source_content=[e for e in sb if e.tag!='{'+W+'}sectPr']
break_index=next(i for i,e in enumerate(db) if e.find('w:pPr/w:sectPr',ns) is not None)
assert break_index==len(source_content),(break_index,len(source_content))
body_before=[E.tostring(e) for e in list(db)[break_index+1:]]
for e in list(db)[:break_index]: db.remove(e)
for i,e in enumerate(source_content): db.insert(i,deepcopy(e))
section=db[break_index].find('w:pPr/w:sectPr',ns)
section.getparent().replace(section,deepcopy(sb.find('w:sectPr',ns)))
assert body_before==[E.tostring(e) for e in list(db)[break_index+1:]],'Paper body changed'
# All dependencies of the copied cover remain the original package objects.
for name,b in source.items():
    if name.startswith(('word/media/','word/embeddings/','word/header','word/footer')) or name in ('word/fontTable.xml','word/theme/theme1.xml','word/numbering.xml'):
        assert parts[name]==b,name
for i,e in enumerate(source_content):
    assert E.tostring(e,method='c14n')==E.tostring(db[i],method='c14n'),i
parts['word/document.xml']=E.tostring(dst,encoding='UTF-8',xml_declaration=True,standalone=True)
with ZipFile(target,'w',ZIP_DEFLATED) as z:
    for name,b in parts.items(): z.writestr(name,b)
assert digest(reference.read_bytes())==reference_hash,'Source title file changed'
audit={'source':str(reference),'source_sha256':digest(reference.read_bytes()),'output':str(target),'copied_original_cover_elements':len(source_content),'cover_xml_equal':True,'cover_graphics_and_embedded_objects_equal':True,'remaining_paper_xml_equal':True,'edited_package_parts':['word/document.xml'],'content_policy':'Original title page copied unchanged, including original wording, blank fields and original date; no personal data filled.'}
(P/'qa/original_title_restore.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(audit,ensure_ascii=False))
