from pathlib import Path
P=Path(__file__).resolve().parents[1]
s=(P/'tools/finalize_cached_fields.py').read_text(encoding='utf-8')
s=s.replace("target=P/'final/ECG_AI_课程论文.docx'; refreshed=P/'qa/word_fields.docx'", "target=P/'final/ECG_AI_课程论文_修订版V2.docx'; refreshed=P/'qa/v2/word_fields.docx'")
s=s.replace("P/'qa/template_package_audit.json'","P/'qa/v2/template_package_audit.json'")
exec(compile(s,str(P/'tools/merge_v2_fields.py'),'exec'),{'__file__':str(P/'tools/finalize_cached_fields.py'),'__name__':'v2_fields'})
