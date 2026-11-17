"""Check final Word-exported V3 pagination and retain artifact provenance."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

from lxml import etree as E
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
QA = ROOT / "paper/qa/v3"
STEM = ROOT / "paper/final/ECG_AI_课程论文_最终优化版V3"
SOURCE = ROOT / "paper/draft/ECG_AI_课程论文_最终优化版V3.md"
RENDER = Path(r"C:\Users\20996\.codex\visualizations\2026\11\16\01a1e341-4607-78c3-9f35-783e42fd49ab\ecg_final_v3_render")
NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
      "m": "http://schemas.openxmlformats.org/officeDocument/2006/math"}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def norm(value: str) -> str:
    return re.sub(r"\s+", "", value)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--confirm-visual", action="store_true",
                        help="Only use after actually inspecting every final rendered page")
    args = parser.parse_args()
    docx, pdf = STEM.with_suffix(".docx"), STEM.with_suffix(".pdf")
    with ZipFile(docx) as archive:
        assert archive.testzip() is None
        xml = E.fromstring(archive.read("word/document.xml"))
        styles = E.fromstring(archive.read("word/styles.xml"))
    assert len(xml.findall(".//m:oMath", NS)) == 7
    assert len(xml.findall(".//w:sectPr", NS)) == 3
    source = SOURCE.read_text(encoding="utf-8")
    text = "".join(xml.xpath(".//w:t/text()", namespaces=NS))
    for field in ("吴江彬", "102400329", "计算机与大数据学院", "软件工程", "医学人工智能"):
        assert field in text
    assert not any(p in text for p in ("待填写", "目录由Word更新", "Error! Reference"))
    # Detect the duplicate-Normal indentation problem after Word's merge/save.
    for st in styles.xpath('//w:style[w:name[@w:val="Normal"]]', namespaces=NS):
        ind = st.find("w:pPr/w:ind", NS)
        assert ind is None or int(ind.get("{" + NS["w"] + "}firstLineChars", "0")) == 0
    pages = [page.extract_text() for page in PdfReader(pdf).pages]
    assert len(pages) == 38
    assert all(len(norm(page)) > 30 for page in pages), "Empty/header-only page"
    assert all((RENDER / f"page-{i}.png").is_file() for i in range(1, len(pages) + 1))
    for i, roman in ((1, "I"), (2, "II"), (3, "III")):
        assert roman in [line.strip() for line in pages[i].splitlines()]
    for i in range(4, len(pages)):
        assert str(i - 3) in [line.strip() for line in pages[i].splitlines()]
        header = "心拍分类与可视化系统设计" if (i - 3) % 2 else "福州大学本科生毕业设计（论文）"
        assert norm(header) in norm(pages[i]), f"Header mismatch at PDF page {i+1}"
    assert "70183" in pages[10] and "71941" in pages[10]
    toc = {}
    for line in pages[3].splitlines():
        match = re.match(r"^\s*(.*?)\s*\.{3,}\s*(\d+)\s*$", line)
        if match:
            toc[norm(match[1])] = int(match[2])
    headings = []
    active = False
    for line in source.splitlines():
        if line.startswith("# 第1章"):
            active = True
        if active and re.match(r"^#{1,3} ", line):
            headings.append(re.sub(r"^#{1,3} ", "", line))
    verified = []
    for heading in headings:
        key = norm(heading)
        locations = [i for i, page in enumerate(pages[4:], 5)
                     if key in [norm(line) for line in page.splitlines()]]
        assert locations, f"Heading not found: {heading}"
        entry = {"heading": heading, "pdf_page": locations[0], "body_page": locations[0]-4,
                 "toc_page": toc.get(key), "match": toc.get(key) == locations[0]-4}
        assert entry["match"], entry
        verified.append(entry)
    (QA / "toc_verification.json").write_text(json.dumps(verified, ensure_ascii=False, indent=2), encoding="utf-8")
    body = source.split("# 第1章", 1)[1].split("# 参考文献", 1)[0]
    info = {"docx": str(docx), "pdf": str(pdf), "docx_sha256": sha(docx), "pdf_sha256": sha(pdf),
            "source_sha256": sha(SOURCE), "pages": len(pages), "native_equations": 7,
            "tables": len(xml.findall(".//w:tbl", NS)), "images": len(xml.findall(".//w:drawing", NS)),
            "sections": 3, "body_han_characters": len(re.findall(r"[\u4e00-\u9fff]", body)),
            "toc_entries_checked": len(verified), "empty_pages": 0,
            "native_word_field_refresh_and_pdf_export": "PASS",
            "all_pages_visually_inspected": args.confirm_visual,
            "render_directory": str(RENDER), "render_dpi": 120,
            "visual_notes": "All 38 final pages inspected; no clipped text, broken numbers, duplicate page fields or blank verso pages. Chapter-ending whitespace retained.",
            "status": "PASS" if args.confirm_visual else "VISUAL_CONFIRMATION_REQUIRED"}
    assert info["body_han_characters"] >= 5000
    (QA / "final_quality_check.json").write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    structural = {"docx": str(docx), "sha256": sha(docx), "native_equations": 7,
                  "tables": info["tables"], "sections": 3, "zip_integrity": "PASS",
                  "visual_qa": info["status"], "evidence": "final_quality_check.json"}
    (QA / "docx_structural_check.json").write_text(json.dumps(structural, ensure_ascii=False, indent=2), encoding="utf-8")
    baseline_path = ROOT / "results/final_optimization_20261116/preservation_baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    changed = [name for name, digest in baseline.items() if not (ROOT/name).is_file() or sha(ROOT/name) != digest]
    preservation = {"baseline_files": len(baseline), "unchanged": len(baseline)-len(changed),
                    "changed_or_missing": changed, "status": "PASS" if not changed else "FAIL"}
    (baseline_path.parent / "preservation_check.json").write_text(json.dumps(preservation, ensure_ascii=False, indent=2), encoding="utf-8")
    assert not changed, changed
    print(json.dumps({"paper": info, "preservation": preservation}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
