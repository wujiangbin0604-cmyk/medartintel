"""Copy Word-updated document/TOC cache while retaining original opaque parts."""
from pathlib import Path
from copy import deepcopy
from zipfile import ZipFile, ZIP_DEFLATED
from lxml import etree as E
import json, hashlib
P=Path(__file__).resolve().parents[1]
target=P/'final/ECG_AI_课程论文.docx'; refreshed=P/'qa/word_fields.docx'
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
with ZipFile(target) as z: base={n:z.read(n) for n in z.namelist()}
with ZipFile(refreshed) as z: updated={n:z.read(n) for n in z.namelist()}
ns={'w':W}
doc=E.fromstring(base['word/document.xml']); udoc=E.fromstring(updated['word/document.xml'])
body=doc.find('w:body',ns); ubody=udoc.find('w:body',ns)
def text(el): return ''.join(el.xpath('.//w:t/text()',namespaces=ns))
def field(el): return ''.join(el.xpath('.//w:instrText/text()',namespaces=ns))
start=next(i for i,e in enumerate(ubody) if 'TOC ' in field(e))
end=next(i for i,e in enumerate(ubody) if i>start and text(e)=='第一章 绪论')
slot=next(e for e in body if 'TOC ' in field(e)); at=list(body).index(slot); body.remove(slot)
for e in list(ubody)[start:end]:
    for node in e.iter():
        assert not any(k.startswith('{'+R+'}') for k in node.attrib),'Unexpected external TOC relationship'
    body.insert(at,deepcopy(e)); at+=1
# Add only Word-generated TOC target bookmarks to the corresponding original headings.
for idx,up in enumerate(ubody.findall('w:p',ns)):
    marks=[m for m in up.findall('w:bookmarkStart',ns) if m.get('{'+W+'}name','').startswith('_Toc')]
    if not marks: continue
    candidates=[p for p in body.findall('w:p',ns) if text(p)==text(up)]
    if not candidates: continue
    p=candidates[-1]
    for m in marks:
        new=deepcopy(m); bid=str(1000+idx); new.set('{'+W+'}id',bid)
        p.insert(1 if len(p) and p[0].tag=='{'+W+'}pPr' else 0,new)
        p.append(E.Element('{'+W+'}bookmarkEnd',{'{'+W+'}id':bid}))
styles=E.fromstring(base['word/styles.xml']); ust=E.fromstring(updated['word/styles.xml'])
ids={x.get('{'+W+'}styleId') for x in styles}
for st in ust:
    sid=st.get('{'+W+'}styleId')
    if sid and sid not in ids: styles.append(st); ids.add(sid)
base['word/document.xml']=E.tostring(doc,encoding='UTF-8',xml_declaration=True,standalone=True)
base['word/styles.xml']=E.tostring(styles,encoding='UTF-8',xml_declaration=True,standalone=True)
with ZipFile(target,'w',ZIP_DEFLATED) as z:
    for n,b in base.items(): z.writestr(n,b)
audit=json.loads((P/'qa/template_package_audit.json').read_text(encoding='utf-8'))
ref=Path(audit['reference'])
assert hashlib.sha256(ref.read_bytes()).hexdigest()==audit['reference_sha256']
for n,ok in audit['preserve_only_equal'].items():
    assert hashlib.sha256(base[n]).hexdigest()==audit['baseline'][n]['sha256'],n
toc=''.join(doc.itertext())
assert '目录将在Word更新' not in toc
print('Word field cache merged; all retained package parts unchanged; source template unchanged.')
