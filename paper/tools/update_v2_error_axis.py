from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
import importlib.util
P=Path(__file__).resolve().parents[1]
png=P/'figures/v2/fig11_errors.png';old=png.read_bytes()
spec=importlib.util.spec_from_file_location('v2_charts',P/'tools/draw_v2_figures.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.FONT_MIN=56;m.error_cases();new=png.read_bytes()
doc=P/'final/ECG_AI_课程论文_修订版V2.docx'
with ZipFile(doc) as z:parts={n:z.read(n) for n in z.namelist()}
found=[n for n,b in parts.items() if b==old];assert len(found)==1,found
parts[found[0]]=new
with ZipFile(doc,'w',ZIP_DEFLATED) as z:
    for n,b in parts.items():z.writestr(n,b)
print('Updated case-image axis spacing only; document text, fields and geometry unchanged.')
