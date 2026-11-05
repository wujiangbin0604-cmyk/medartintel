from pathlib import Path
import json,hashlib
P=Path(__file__).resolve().parents[1]
f=P/'qa/original_title_restore.json'; audit=json.loads(f.read_text(encoding='utf-8'))
audit.update({'pages':24,'cover_pixel_equal_to_original':True,'unchanged_body_pages':list(range(2,25)),'render_pdf':str(P/'qa/original_title_final.pdf'),'output_sha256':hashlib.sha256((P/'final/ECG_AI_课程论文.docx').read_bytes()).hexdigest()})
f.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
f=P/'qa/final_qa.json'; qa=json.loads(f.read_text(encoding='utf-8'))
qa['docx_sha256']=audit['output_sha256']; qa['original_title_copied_verbatim']=True
qa['visual_qa']['latest_revision']='Copied original cover exactly; pixel comparison against original rendered title has no differences. Pages 2–24 pixel-identical to previously inspected final pages.'
qa['visual_qa']['limitations']='Original title wording, empty fields and date intentionally retained at user request. Original experiment figures include English labels.'
f.write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
f=P/'paper_review.md'; s=f.read_text(encoding='utf-8')
s=s.replace('专业栏因未提供保留空白。','封面按最新要求直接保留原title的全部空栏。')
s=s.replace('封面填写吴江彬、102400329、计算机与大数据学院、2024级、胡桓；专业保持空栏。','根据用户最新更正，原title整页直接复制，原课程名称、空栏和2026年10月5日日期均保留，不另行填写。复制后封面与原页渲染结果逐像素一致，正文第2—24页与此前终稿逐像素一致。')
f.write_text(s,encoding='utf-8')
f=P/'qa/artifact.md'; s=f.read_text(encoding='utf-8')
s='# 最新封面要求\n\n用户更正：开头直接复制原报告title.docx整页，不制作、不改字、不填空栏、不改日期。此要求覆盖下方早期编辑槽约定；正文保持不变。复制后的20个原始内容元素规范XML完全相同，图形/OLE依赖相同，封面渲染逐像素相同，正文第2—24页逐像素相同。详见original_title_restore.json。\n\n'+s
f.write_text(s,encoding='utf-8')
print('Latest original-title requirement and visual QA recorded.')
