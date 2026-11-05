from pathlib import Path
import json
P=Path(__file__).resolve().parents[1]
f=P/'qa/colored_title_audit.json'; a=json.loads(f.read_text(encoding='utf-8'))
a.update({'pages':24,'cover_visual_inspection':'passed: original red school-name graphics displayed; course heading exact and on one line','unchanged_body_pages':list(range(2,25)),'body_pixels_equal_to_previous_final':True,'render_pdf':str(P/'qa/colored_title_final.pdf')})
f.write_text(json.dumps(a,ensure_ascii=False,indent=2),encoding='utf-8')
f=P/'qa/final_qa.json'; j=json.loads(f.read_text(encoding='utf-8'))
j['docx_sha256']=a['docx_sha256']; j['original_title_copied_verbatim']=False
j['authorized_cover_changes']=['Restore color display of the four original red school-name images','Course heading 医学人工智能课程项目论文']
j['visual_qa']['latest_revision']='Red native logo restored and exact course heading verified on the rendered first page; body pages 2–24 pixel-identical to prior inspected output.'
f.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
for path in ['qa/artifact.md','paper_review.md']:
    f=P/path; s=f.read_text(encoding='utf-8')
    note='用户最新封面要求已完成：保留原模板图形及布局，解除4个校名图片的黑白显示属性以恢复原红色，将课程名称改为“医学人工智能课程项目论文”。只编辑封面两个段落，未改原图、OLE、空栏或日期；正文第2—24页逐像素一致。此说明覆盖早期完全不改文字/显示属性的封面约定。'
    f.write_text('# 彩色校名与课程名称最终更正\n\n'+note+'\n\n'+s,encoding='utf-8')
print('Colored title QA and current cover requirements recorded.')
