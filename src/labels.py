"""Explicit, case-sensitive rules; never infer a label from a waveform."""

ANNOTATION_SOURCE = "https://physionet.org/static/lightwave/doc/annotations.html"
MAPPING_SOURCE = "https://doi.org/10.1109/TBME.2004.827359"
GROUPS = ("N", "S", "V", "F", "Q")
AAMI_MAP = {symbol: group for group, symbols in {
    "N": ("N", "L", "R", "e", "j"),
    "S": ("A", "a", "J", "S"),
    "V": ("V", "E"), "F": ("F",), "Q": ("/", "f", "Q"),
}.items() for symbol in symbols}
BEAT_ZH = {
    "N": "正常心拍", "L": "左束支传导阻滞心拍", "R": "右束支传导阻滞心拍",
    "e": "房性逸搏", "j": "交界性逸搏", "A": "房性期前收缩",
    "a": "伴差异传导的房性期前收缩", "J": "交界性期前收缩",
    "S": "室上性期前或异位心拍", "V": "室性期前收缩", "E": "室性逸搏",
    "F": "室性与正常心拍融合", "/": "起搏心拍", "f": "起搏与正常心拍融合",
    "Q": "无法分类心拍", "B": "未特指的束支传导阻滞心拍",
    "r": "R-on-T 室性期前收缩", "n": "室上性逸搏", "?": "学习期间未分类心拍",
}
NONBEAT_ZH = {
    "+": "节律改变（详见 aux_note）", "~": "信号质量改变（保留 subtype）",
    "|": "孤立的类 QRS 伪迹", '"': "注释文本", "[": "心室扑动/颤动开始",
    "]": "心室扑动/颤动结束", "!": "心室扑动波（非逐心拍标注）",
    "x": "未下传 P 波（阻滞型房性期前收缩）", "(": "波形起点", ")": "波形终点",
    "p": "P 波峰", "t": "T 波峰", "u": "U 波峰", "`": "PQ 交界点（旧代码）",
    "'": "J 点（旧代码）", "^": "未夺获的起搏器伪迹", "s": "ST 段改变",
    "T": "T 波改变", "*": "收缩期", "D": "舒张期", "=": "测量标注",
    "@": "外部链接", " ": "非实际标注",
}
GROUP_ZH = {"N": "N 组（正常/束支阻滞/部分逸搏）", "S": "室上性异位心拍",
            "V": "室性异位心拍", "F": "融合心拍", "Q": "起搏或无法分类心拍"}


def describe(symbol):
    if symbol in AAMI_MAP:
        return {"annotation_kind": "mapped_beat", "aami_group": AAMI_MAP[symbol],
                "meaning_zh": BEAT_ZH[symbol]}
    if symbol in NONBEAT_ZH:
        return {"annotation_kind": "non_beat", "aami_group": "",
                "meaning_zh": NONBEAT_ZH[symbol]}
    if symbol in BEAT_ZH:
        return {"annotation_kind": "unmapped_beat", "aami_group": "",
                "meaning_zh": BEAT_ZH[symbol]}
    return {"annotation_kind": "unknown", "aami_group": "",
            "meaning_zh": "未识别符号：需核查数据库说明，不自动归组"}
