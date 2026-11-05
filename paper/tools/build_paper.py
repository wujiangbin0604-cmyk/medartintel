"""Build the audited course paper while preserving the supplied cover package."""
from pathlib import Path
from copy import deepcopy
from zipfile import ZipFile, ZIP_DEFLATED
import csv, hashlib, json, re, shutil
from lxml import etree as E
from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[2]
PAPER = ROOT / 'paper'
REF = Path(r'C:\Users\20996\Downloads\报告title.docx')
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
NS = {'w': W, 'r': R}
def sha(b): return hashlib.sha256(b).hexdigest()
def xml(b): return E.fromstring(b)
def dump(x): return E.tostring(x, encoding='UTF-8', xml_declaration=True, standalone=True)

FIGS = [
('fig01_workflow.png','figures/12_final_report/10_project_workflow.png','第一章1.4'),
('fig02_filter.png','figures/07_preprocessing/200_raw_vs_filtered_first10s.png','第二章2.3'),
('fig03_window.png','figures/preprocessing/200_window_extraction.png','第二章2.3'),
('fig04_support.png','figures/12_final_report/02_class_support_and_subject_coverage.png','第二章2.5'),
('fig05_cnn.png',None,'第三章3.3'),
('fig06_results.png','figures/12_final_report/01_task_model_performance.png','第五章5.1'),
('fig07_nv_confusion.png','figures/08_binary_classification/test_confusion_matrix_cnn_1d.png','第五章5.1'),
('fig08_concentration.png','figures/11_four_class_diagnosis/top_subject_class_concentration.png','第五章5.3'),
('fig09_weights.png','figures/11_four_class_diagnosis/cnn_weight_strategies_train_val.png','第五章5.4'),
('fig10_cv.png','figures/11_four_class_diagnosis/group_cv_fold_metrics.png','第五章5.5'),
('fig11_errors.png','figures/11_four_class_diagnosis/cnn_test_error_waveforms_descriptive_only.png','第五章5.6'),
('fig12_architecture.png',None,'第六章6.1'),
('fig13_workbench.png','web/docs/visual_fidelity/iteration2/ecg_1672x941.png','第六章6.2'),
('fig14_comparison.png','web/docs/visual_fidelity/iteration2/comparison_1672x941.png','第六章6.2'),
('fig15_experiments.png','web/docs/visual_fidelity/iteration2/experiments_1672x941.png','第六章6.3'),
]

def make_diagram(name, boxes, subtitle):
    im=Image.new('RGB',(1800,650),'white'); d=ImageDraw.Draw(im)
    font=ImageFont.truetype(r'C:\Windows\Fonts\simsun.ttc',31)
    small=ImageFont.truetype(r'C:\Windows\Fonts\simsun.ttc',27)
    n=len(boxes); gap=36; bw=(1720-gap*(n-1))//n
    for i,lines in enumerate(boxes):
        x=40+i*(bw+gap); y=130
        d.rounded_rectangle((x,y,x+bw,y+300),radius=8,fill='#f2f5f7',outline='#445c6d',width=3)
        for k,line in enumerate(lines):
            b=d.textbbox((0,0),line,font=font); d.text((x+(bw-(b[2]-b[0]))/2,y+45+k*57),line,font=font,fill='black')
        if i<n-1:
            xx=x+bw+5; yy=y+150
            d.line((xx,yy,xx+gap-10,yy),fill='#445c6d',width=4)
            d.polygon([(xx+gap-10,yy),(xx+gap-23,yy-9),(xx+gap-23,yy+9)],fill='#445c6d')
    b=d.textbbox((0,0),subtitle,font=small)
    d.text(((1800-(b[2]-b[0]))/2,520),subtitle,font=small,fill='#333333')
    im.save(PAPER/'figures'/name)

def prepare():
    for name,src,section in FIGS:
        if src: shutil.copy2(ROOT/src,PAPER/'figures'/name)
    make_diagram('fig05_cnn.png',[
        ['单导联输入','1 × 253'], ['Conv 1→16','核7 + ReLU','MaxPool 2'],
        ['Conv 16→32','核5 + ReLU','MaxPool 2'], ['Conv 32→64','核3 + ReLU','平均池化'],
        ['Linear 64→K','输出 logits','K = 2 或 4']],
        '时间长度 253 → 126 → 63 → 1   参数量 9058 或 9188   来源 src/models/classifiers.py')
    make_diagram('fig12_architecture.png',[
        ['本地数据层','WFDB 与标注','工件与实验表'], ['ECGStore','连续信号滤波','253点与标准化'],
        ['ModelRegistry','LR / RF / CNN','类别与分数'], ['FastAPI 接口','数据与推理','结果响应'],
        ['React 与 Umi','Ant Design','ECharts']],
        '用户选拍 → 后端读取与预处理 → 已有模型推理 → API 返回 → 界面展示')
    src=PAPER/'draft/ECG_AI_课程论文初稿.md'
    s=src.read_text(encoding='utf-8')
    weight='| 权重方案 | Accuracy | Macro-F1 | S Recall | F Recall | N Recall |\n|---|---|---|---|---|---|\n'
    rows=list(csv.DictReader((ROOT/'results/classification/nsvf44_v1/diagnosis/weight_strategy_train_val_metrics.csv').open(encoding='utf-8-sig')))
    cls=list(csv.DictReader((ROOT/'results/classification/nsvf44_v1/diagnosis/weight_strategy_class_metrics.csv').open(encoding='utf-8-sig')))
    for st,cn in [('unweighted','无权重'),('sqrt_inverse','平方根平滑'),('capped_inverse_10','截断逆频率'),('full_inverse','完整逆频率')]:
        row=next(x for x in rows if x['strategy']==st and x['split']=='val')
        cr={x['class']:x for x in cls if x['strategy']==st and x['split']=='val'}
        weight+='| '+cn+' | '+' | '.join(f'{float(x):.4f}' for x in [row['accuracy'],row['macro_f1_present_classes'],cr['S']['recall'],cr['F']['recall'],cr['N']['recall']])+' |\n'
    s=s.replace('<!--WEIGHT_TABLE-->',weight.strip())
    refs=(PAPER/'references/verified_references.md').read_text(encoding='utf-8')
    entries=re.findall(r'^\[\d+\] .+$',refs,re.M)
    s=s.replace('<!--REFERENCES-->','\n\n'.join(entries))
    src.write_text(s,encoding='utf-8')
    idx=['# 正文图像索引','', '| 图号 | 图题 | 本地论文文件 | 实际来源 | 正文位置 |','|---|---|---|---|---|']
    for i,(name,source,section) in enumerate(FIGS,1):
        cap=re.search(r'!\[(图'+str(i)+r' .+?)\]',s).group(1)
        origin=source or ('paper/tools/build_paper.py 据src/models/classifiers.py绘制' if i==5 else 'paper/tools/build_paper.py 据web/backend与前端配置绘制')
        idx.append(f'| {i} | {cap} | {name} | {origin} | {section} |')
    (PAPER/'figures/figure_index.md').write_text('\n'.join(idx)+'\n',encoding='utf-8')
    return s

def make_style(doc,name,size,font='宋体',bold=False):
    st=doc.styles.add_style(name,WD_STYLE_TYPE.PARAGRAPH)
    st.base_style=doc.styles['Normal']; st.font.name='Times New Roman'; st.font.size=Pt(size); st.font.bold=bold; st.font.color.rgb=RGBColor(0,0,0)
    st.element.get_or_add_rPr().append(E.Element(qn('w:rFonts'),{qn('w:eastAsia'):font,qn('w:ascii'):'Times New Roman',qn('w:hAnsi'):'Times New Roman'}))
    pf=st.paragraph_format; pf.space_before=Pt(0); pf.space_after=Pt(6); pf.line_spacing=1.5
    pf.widow_control=True
    return st

M='http://schemas.openxmlformats.org/officeDocument/2006/math'
def mr(text):
    r=E.Element('{'+M+'}r'); E.SubElement(r,'{'+M+'}t').text=text; return r
def sub(text,index):
    v=E.Element('{'+M+'}sSub'); e=E.SubElement(v,'{'+M+'}e'); e.append(mr(text))
    e=E.SubElement(v,'{'+M+'}sub'); e.append(mr(index)); return v
def frac(numerator,denominator):
    f=E.Element('{'+M+'}f')
    for tag,items in [('num',numerator),('den',denominator)]:
        e=E.SubElement(f,'{'+M+'}'+tag)
        for item in items: e.append(mr(item) if isinstance(item,str) else item)
    return f
def equation(d,index):
    if index==1: items=[sub('x','i'),'[j] = ',sub('s','f'),'[',sub('r','i'),' − 108 + j]， j = 0，…，252']
    elif index==2: items=[sub('z','i'),'[j] = ',frac([sub('x','i'),'[j] − ',sub('μ','train')],[sub('σ','train')])]
    elif index==3: items=['L = −',frac([sub('Σ','i'),' ',sub('w','yᵢ'),' ln ',sub('p','i,yᵢ')],[sub('Σ','i'),' ',sub('w','yᵢ')])]
    elif index==4: items=['Accuracy = ',frac([sub('Σ','c'),' ',sub('M','c,c')],['n'])]
    elif index==5: items=[sub('Precision','c'),' = ',frac([sub('TP','c')],[sub('TP','c'),' + ',sub('FP','c')]),'， ',sub('Recall','c'),' = ',frac([sub('TP','c')],[sub('TP','c'),' + ',sub('FN','c')])]
    elif index==6: items=[sub('F1','c'),' = ',frac(['2 ',sub('Precision','c'),' ',sub('Recall','c')],[sub('Precision','c'),' + ',sub('Recall','c')])]
    else: items=['Macro-F1 = ',frac(['1'],['K']),' ',sub('Σ','c'),' ',sub('F1','c')]
    p=d.add_paragraph(style='ECGEquation'); om=E.SubElement(p._p,'{'+M+'}oMath')
    for item in items: om.append(mr(item) if isinstance(item,str) else item)
    p.add_run('  （'+str(index)+'）')

def body_doc(s):
    d=Document()
    for name,size,font,bold in [('ECGBody',12,'宋体',False),('ECGHeading1',16,'黑体',True),('ECGHeading2',14,'黑体',True),('ECGTitle',18,'黑体',True),('ECGCaption',10.5,'宋体',False),('ECGTable',10,'宋体',False),('ECGReference',10.5,'宋体',False),('ECGEquation',11,'宋体',False),('ECGFigure',10.5,'宋体',False)]:
        st=make_style(d,name,size,font,bold)
        if name=='ECGBody': st.paragraph_format.first_line_indent=Pt(24); st.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
        if name.startswith('ECGHeading'):
            st.paragraph_format.keep_with_next=True; st.paragraph_format.space_before=Pt(12); st.paragraph_format.space_after=Pt(8)
            st.element.get_or_add_pPr().append(E.Element(qn('w:outlineLvl'),{qn('w:val'):'0' if name.endswith('1') else '1'}))
        if name in ('ECGCaption','ECGEquation'): st.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER
        if name=='ECGCaption': st.paragraph_format.line_spacing=1.15; st.paragraph_format.space_after=Pt(8)
        if name=='ECGFigure': st.paragraph_format.alignment=WD_ALIGN_PARAGRAPH.CENTER; st.paragraph_format.line_spacing=1; st.paragraph_format.keep_with_next=True; st.paragraph_format.space_after=Pt(4)
        if name=='ECGTable': st.paragraph_format.line_spacing=1.15; st.paragraph_format.space_after=Pt(3)
        if name=='ECGReference': st.paragraph_format.line_spacing=1.2; st.paragraph_format.left_indent=Pt(20); st.paragraph_format.first_line_indent=Pt(-20)
    lines=s.splitlines(); i=0; refmode=False
    while i<len(lines):
        line=lines[i].strip(); i+=1
        if not line: continue
        if line=='<!--TOC-->':
            p=d.add_paragraph('目录','ECGTitle'); p.paragraph_format.page_break_before=True; p.alignment=1
            p=d.add_paragraph(); p.style='ECGBody'; p.paragraph_format.first_line_indent=Pt(0)
            for kind,value in [('begin',None),(None,'TOC \\t "ECGHeading1,1,ECGHeading2,2" \\h \\z'),('separate',None)]:
                r=p.add_run(); el=OxmlElement('w:instrText' if kind is None else 'w:fldChar')
                if kind: el.set(qn('w:fldCharType'),kind)
                else: el.text=value; el.set(qn('xml:space'),'preserve')
                r._r.append(el)
            p.add_run('目录将在Word更新')
            r=p.add_run(); el=OxmlElement('w:fldChar'); el.set(qn('w:fldCharType'),'end'); r._r.append(el)
            continue
        if line.startswith('# '):
            val=line[2:]; first=(len(d.paragraphs)==0)
            sty='ECGTitle' if first else 'ECGHeading1'
            p=d.add_paragraph(val,sty)
            if first: p.alignment=1; p.paragraph_format.space_after=Pt(18)
            else: p.paragraph_format.page_break_before=val.startswith('第一章')
            if val=='参考文献': refmode=True
            continue
        if line.startswith('## '):
            val=line[3:]; p=d.add_paragraph(val,'ECGHeading2' if re.match(r'\d',val) else 'ECGTitle')
            if val=='摘要': p.alignment=1
            continue
        if line.startswith('!['):
            m=re.match(r'!\[(.+)\]\((.+)\)',line); path=(PAPER/'draft'/m[2]).resolve()
            im=Image.open(path); width=6.1; height=width*im.height/im.width
            if height>5.8: width*=5.8/height
            p=d.add_paragraph(style='ECGFigure'); p.add_run().add_picture(str(path),width=Inches(width))
            d.add_paragraph(m[1],'ECGCaption'); continue
        if line.startswith('|'):
            data=[line]
            while i<len(lines) and lines[i].strip().startswith('|'): data.append(lines[i].strip()); i+=1
            data=[x for x in data if not re.match(r'^\|[\s:|\-]+$',x)]
            cells=[[v.strip() for v in x.strip('|').split('|')] for x in data]
            table=d.add_table(rows=0, cols=len(cells[0])); table.autofit=False
            if len(cells[0])==4: widths=[.95,1.6,1.6,1.95]
            elif len(cells[0])==3: widths=[.7,1.6,3.8]
            else: widths=[6.1/len(cells[0])]*len(cells[0])
            for col,wid in zip(table.columns,widths): col.width=Inches(wid)
            borders=OxmlElement('w:tblBorders')
            for side in ['top','left','bottom','right','insideH','insideV']:
                el=OxmlElement('w:'+side); el.set(qn('w:val'),'single'); el.set(qn('w:sz'),'4'); el.set(qn('w:color'),'D9D9D9'); borders.append(el)
            table._tbl.tblPr.append(borders)
            for rownum,vals in enumerate(cells):
                row=table.add_row(); trpr=row._tr.get_or_add_trPr(); trpr.append(OxmlElement('w:cantSplit'))
                if rownum==0: trpr.append(OxmlElement('w:tblHeader'))
                for k,(cell,txt) in enumerate(zip(row.cells,vals)):
                    cell.width=Inches(widths[k]); cell.vertical_alignment=1
                    tcpr=cell._tc.get_or_add_tcPr(); marg=OxmlElement('w:tcMar')
                    for side in ['top','left','bottom','right']:
                        el=OxmlElement('w:'+side); el.set(qn('w:w'),'90'); el.set(qn('w:type'),'dxa'); marg.append(el)
                    tcpr.append(marg)
                    if rownum==0:
                        sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),'E9EEF2'); tcpr.append(sh)
                    p=cell.paragraphs[0]; p.style='ECGTable'; p.alignment=WD_ALIGN_PARAGRAPH.CENTER
                    rr=p.add_run(txt); rr.bold=(rownum==0)
                    if rownum<len(cells)-1: p.paragraph_format.keep_with_next=True
            continue
        if line.startswith('$$ '): equation(d,int(re.search(r'（(\d+)）',line).group(1))); continue
        if re.match(r'^表\d+\s',line):
            p=d.add_paragraph(line,'ECGCaption'); p.paragraph_format.keep_with_next=True; continue
        p=d.add_paragraph(line,'ECGReference' if refmode else 'ECGBody')
        if line.endswith('：'): p.paragraph_format.keep_with_next=True
        if line.startswith('关键词'): p.paragraph_format.first_line_indent=Pt(0)
    d.save(PAPER/'qa/body.docx')

def cover_replace(p,text,size=None):
    runs=p.findall('w:r',NS); tnodes=p.findall('.//w:t',NS)
    if not tnodes:
        r=E.SubElement(p,qn('w:r')); rp=E.SubElement(r,qn('w:rPr')); E.SubElement(rp,qn('w:rFonts'),{qn('w:eastAsia'):'宋体'}); E.SubElement(rp,qn('w:sz'),{qn('w:val'):str(size or 28)})
        tnodes=[E.SubElement(r,qn('w:t'))]
    tnodes[0].text=text
    for t in tnodes[1:]: t.text=''
    if size:
        for r in runs:
            rp=r.find('w:rPr',NS)
            if rp is None: rp=E.SubElement(r,qn('w:rPr'))
            sz=rp.find('w:sz',NS)
            if sz is None: sz=E.SubElement(rp,qn('w:sz'))
            sz.set(qn('w:val'),str(size))

def merge_package():
    with ZipFile(REF) as z: parts={n:z.read(n) for n in z.namelist()}
    baseline={n:{'bytes':len(b),'sha256':sha(b)} for n,b in parts.items()}
    tree=xml(parts['word/document.xml']); body=tree.find('w:body',NS); ps=body.findall('w:p',NS)
    # Retain the source cover with the user's two explicit color/title changes.
    for pic in ps[1].findall('.//{urn:schemas-microsoft-com:vml}imagedata'):
        pic.attrib.pop('grayscale',None)
        pic.attrib.pop('bilevel',None)
    title_nodes=ps[3].findall('.//w:t',NS)
    title_nodes[0].text='医学人工智能课程项目论文'
    for node in title_nodes[1:]: node.text=''
    sect=body.find('w:sectPr',NS); body.remove(sect)
    bp=E.SubElement(body,qn('w:p')); pp=E.SubElement(bp,qn('w:pPr')); pp.append(deepcopy(sect))
    with ZipFile(PAPER/'qa/body.docx') as bzip: bpkg={n:bzip.read(n) for n in bzip.namelist()}
    btree=xml(bpkg['word/document.xml']); bbody=btree.find('w:body',NS)
    relroot=xml(parts['word/_rels/document.xml.rels']); oldids={x.get('Id') for x in relroot}; relmap={}
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    for rel in xml(bpkg['word/_rels/document.xml.rels']):
        if rel.get('Type','').endswith('/image'):
            k=1
            while f'rIdECG{k}' in oldids: k+=1
            rid=f'rIdECG{k}'; oldids.add(rid); relmap[rel.get('Id')]=rid
            target=rel.get('Target'); name='ecg_'+Path(target).name
            parts['word/media/'+name]=bpkg['word/'+target]
            E.SubElement(relroot,'{'+relns+'}Relationship',Id=rid,Type=rel.get('Type'),Target='media/'+name)
    for el in list(bbody):
        if el.tag==qn('w:sectPr'): continue
        for node in el.iter():
            for attr,val in list(node.attrib.items()):
                if attr.startswith('{'+R+'}') and val in relmap: node.set(attr,relmap[val])
        body.append(deepcopy(el))
    # The cover is retained. Appended course-paper pages get neutral headers.
    bodysect=deepcopy(sect)
    for el in list(bodysect):
        if el.tag in (qn('w:headerReference'),qn('w:footerReference')): bodysect.remove(el)
    for typ in ['default','even']:
        E.SubElement(bodysect,qn('w:headerReference'),{qn('w:type'):typ,qn('r:id'):'rIdECGHeader'})
        E.SubElement(bodysect,qn('w:footerReference'),{qn('w:type'):typ,qn('r:id'):'rIdECGFooter'})
    body.append(bodysect)
    header=E.Element(qn('w:hdr'),nsmap={'w':W}); E.SubElement(header,qn('w:p'))
    footer=E.Element(qn('w:ftr'),nsmap={'w':W}); fp=E.SubElement(footer,qn('w:p')); fpp=E.SubElement(fp,qn('w:pPr')); E.SubElement(fpp,qn('w:jc'),{qn('w:val'):'center'})
    rr=E.SubElement(fp,qn('w:r')); rp=E.SubElement(rr,qn('w:rPr')); E.SubElement(rp,qn('w:sz'),{qn('w:val'):'18'})
    E.SubElement(rr,qn('w:fldChar'),{qn('w:fldCharType'):'begin'}); rr=E.SubElement(fp,qn('w:r')); E.SubElement(rr,qn('w:instrText')).text='PAGE'; rr=E.SubElement(fp,qn('w:r')); E.SubElement(rr,qn('w:fldChar'),{qn('w:fldCharType'):'end'})
    parts['word/ecg_header.xml']=dump(header); parts['word/ecg_footer.xml']=dump(footer)
    for kind in ['header','footer']:
        E.SubElement(relroot,'{'+relns+'}Relationship',Id='rIdECG'+kind.title(),Type=R+'/'+kind,Target='ecg_'+kind+'.xml')
    parts['word/document.xml']=dump(tree); parts['word/_rels/document.xml.rels']=dump(relroot)
    styles=xml(parts['word/styles.xml'])
    for st in xml(bpkg['word/styles.xml']):
        if st.get(qn('w:styleId'),'').startswith('ECG'): styles.append(deepcopy(st))
    cst=E.SubElement(styles,qn('w:style'),{qn('w:type'):'paragraph',qn('w:styleId'):'ECGCoverTitle'})
    E.SubElement(cst,qn('w:name'),{qn('w:val'):'Title'}); E.SubElement(cst,qn('w:basedOn'),{qn('w:val'):'Normal'})
    for st in styles.findall('w:style',NS):
        nm=st.find('w:name',NS)
        if nm is not None and nm.get(qn('w:val'),'').lower() in ('toc 1','toc 2'):
            rp=st.find('w:rPr',NS)
            if rp is None: rp=E.SubElement(st,qn('w:rPr'))
            sz=rp.find('w:sz',NS)
            if sz is None: sz=E.SubElement(rp,qn('w:sz'))
            sz.set(qn('w:val'),'21')
            pp=st.find('w:pPr',NS)
            if pp is None: pp=E.SubElement(st,qn('w:pPr'))
            sp=pp.find('w:spacing',NS)
            if sp is None: sp=E.SubElement(pp,qn('w:spacing'))
            sp.attrib.update({qn('w:before'):'0',qn('w:after'):'0',qn('w:line'):'260',qn('w:lineRule'):'auto'})
    parts['word/styles.xml']=dump(styles)
    settings=xml(parts['word/settings.xml']); up=settings.find('w:updateFields',NS)
    if up is None: up=E.SubElement(settings,qn('w:updateFields'))
    up.set(qn('w:val'),'true'); parts['word/settings.xml']=dump(settings)
    ct=xml(parts['[Content_Types].xml']); ctns='http://schemas.openxmlformats.org/package/2006/content-types'
    if not any(e.get('Extension')=='png' for e in ct): E.SubElement(ct,'{'+ctns+'}Default',Extension='png',ContentType='image/png')
    for kind in ['header','footer']:
        E.SubElement(ct,'{'+ctns+'}Override',PartName='/word/ecg_'+kind+'.xml',ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.'+kind+'+xml')
    parts['[Content_Types].xml']=dump(ct)
    output=PAPER/'final/ECG_AI_课程论文.docx'
    with ZipFile(output,'w',ZIP_DEFLATED) as z:
        for n,b in parts.items(): z.writestr(n,b)
    edits={'word/document.xml','word/styles.xml','word/settings.xml','word/_rels/document.xml.rels','[Content_Types].xml'}
    preserved={n:sha(parts[n])==info['sha256'] for n,info in baseline.items() if n not in edits}
    assert all(preserved.values()), 'Template opaque package changed'
    audit={'reference':str(REF),'reference_sha256':sha(REF.read_bytes()),'baseline':baseline,'preserve_only_equal':preserved,'editable_parts':sorted(edits),'new_parts':sorted(set(parts)-set(baseline))}
    (PAPER/'qa/template_package_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    return output

if __name__=='__main__':
    s=prepare(); body_doc(s); out=merge_package()
    chinese=len(re.findall(r'[\u4e00-\u9fff]',s)); ch5=s.split('# 第五章')[1].split('# 第六章')[0]
    counts={'chinese_characters_all_including_tables_refs':chinese,'chapter5_chinese_characters':len(re.findall(r'[\u4e00-\u9fff]',ch5)),'figures':15,'tables':8}
    (PAPER/'qa/content_counts.json').write_text(json.dumps(counts,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out),**counts},ensure_ascii=False))
