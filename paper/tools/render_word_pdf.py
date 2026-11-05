"""Use bundled render_docx rasterizer with a native-Word PDF conversion result."""
from pathlib import Path
import importlib.util, os, sys, tempfile
P=Path(__file__).resolve().parents[1]
runtime=Path(r'C:\Users\20996\.cache\codex-runtimes\codex-primary-runtime\dependencies')
poppler=runtime/'native/poppler/Library/bin'
os.environ['PATH']=str(poppler)+os.pathsep+os.environ['PATH']
tmp=P/'qa/temp'; tmp.mkdir(exist_ok=True); tempfile.tempdir=str(tmp)
skill=Path(r'C:\Users\20996\.codex\plugins\cache\openai-primary-runtime\documents\26.1026.10807\skills\documents\render_docx.py')
spec=importlib.util.spec_from_file_location('bundled_render_docx',skill); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
pdf=Path(sys.argv[1]).resolve(); out=Path(sys.argv[2]).resolve()
module.convert_to_pdf=lambda *args,**kwargs:(str(pdf),'Native Microsoft Word export; LibreOffice unavailable on this Windows host.')
pages=module.rasterize(str(P/'final/ECG_AI_课程论文.docx'),str(out),dpi=144,verbose=False,emit_pdf=False)
print(f'Bundled render_docx.py rasterize completed: {len(pages)} pages at 144 dpi.')
