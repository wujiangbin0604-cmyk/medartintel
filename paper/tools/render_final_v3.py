"""Rasterize the actual native-Word PDF through the bundled DOCX renderer."""
from pathlib import Path
import importlib.util
import os

ROOT = Path(__file__).resolve().parents[2]
DOCX = ROOT / "paper/final/ECG_AI_课程论文_最终优化版V3.docx"
PDF = DOCX.with_suffix(".pdf")
RENDER = Path(r"C:\Users\20996\.codex\visualizations\2026\11\16\01a1e341-4607-78c3-9f35-783e42fd49ab\ecg_final_v3_render")
runtime = Path(r"C:\Users\20996\.cache\codex-runtimes\codex-primary-runtime\dependencies")
os.environ["PATH"] = str(runtime / "native/poppler/Library/bin") + os.pathsep + os.environ["PATH"]
script = Path(r"C:\Users\20996\.codex\plugins\cache\openai-primary-runtime\documents\26.1112.11217\skills\documents\render_docx.py")
spec = importlib.util.spec_from_file_location("bundled_docx_renderer", script)
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)
renderer.convert_to_pdf = lambda *args, **kwargs: (str(PDF), "Actual Microsoft Word field-refresh and PDF export")
pages = renderer.rasterize(str(DOCX), str(RENDER), dpi=120, verbose=False, emit_pdf=False)
print(f"Rendered {len(pages)} actual PDF pages at 120 dpi")
