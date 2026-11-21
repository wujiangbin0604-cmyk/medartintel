"""Build a delivery note from this session's actual verification evidence."""
import csv
from datetime import datetime
import json
import subprocess
import xml.etree.ElementTree as ET
import numpy as np
from research_extensions.protect import ROOT, sha256


def read(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8'))


def main():
    validation = ROOT / 'research_extensions/validation'
    audit = read('research_extensions/validation/revalidation_20261119_artifacts.json')
    browser = read('research_extensions/validation/revalidation_20261119_browser/results.json')
    protection = read('research_extensions/protection_verification.json')
    summary = read('research_extensions/rhythm_fusion/results/cv_cpu_v1/summary.json')
    selective = read('research_extensions/uncertainty/results/revalidation_20261119/cv_cpu_v1/summary.json')
    tests = ET.parse(validation / 'revalidation_20261119_pytest.xml').getroot().find('testsuite').attrib
    assert audit['status'] == 'passed' and audit['full_checkpoint_inference_reproduced']
    assert protection['passed'] and browser['stats']['unexpected'] == 0 and browser['stats']['skipped'] == 0
    fmt = lambda xs: f'{np.mean(xs):.4f} ± {np.std(xs, ddof=1):.4f}'
    text = ['# ECG-AI 本次交付与独立复核（2026-11-19）', '',
        '本次发现 `E:/医学人工智能` 已有与请求对应的研究实现及完整实验，因其不在当前可写范围，保留原目录并迁入 `D:/生物信息学/medartintel-local` 进行复核和补充。原仓库 origin 为用户指定 medartintel，HEAD 为 `6fbb598802f1f4aa2f61b475798ab6cfb5299e9f`；首次只读 Git 检查已存在研究扩展、网页及部署修改和论文 QA 未跟踪文件。本次没有覆盖这些历史成果、没有提交或推送。', '',
        '**来源界限：60 组正式训练为继承工件，本次没有重训这 60 组；本次真正执行的是所有权重的完整评价/校准推理复算、全部 RR 对齐复算、新的四模型训练 Smoke Test、拒识复算、13 对 PNG/SVG 重绘、Python 回归、前端构建和浏览器回归。**', '',
        '## A. 工程交付', '',
        '|内容|入口|', '|---|---|',
        '|RR 特征/掩码及逐拍追溯|rhythm_fusion/src/data.py；rhythm_fusion/data/alignment.csv / audit.json|',
        '|独立 RRMLP 与 RhythmMorphologyCNN|rhythm_fusion/src/models.py；原 src/models/classifiers.py 保持原样|',
        '|训练与模型加载|rhythm_fusion/src/run.py；results/*/fold*/seed*/A*/best.pt；web/backend/rhythm_lab.py|',
        '|API|/api/rhythm/summary、/samples、/beat|',
        '|实验室页面|web/frontend/src/pages/rhythm-lab/；路由 /rhythm-lab|',
        '|教学联动|HeartbeatHunter 专家答案之后携带 record_id / annotation_sample 跳转实验室|',
        '|本次新增审计工具|revalidate.py、revalidate_smoke.py、revalidate_analysis.py、delivery_20261119.py|',
        '|本次最小改动|figures.py 支持独立输出目录；两份浏览器测试支持隔离截图/数据库；playwright.revalidation.config.ts|', '',
        '本机启动：在副本根目录执行 `.venv/Scripts/python.exe -B -m uvicorn web.backend.production:app --host 127.0.0.1 --port 8142`，访问 `http://127.0.0.1:8142/rhythm-lab`。本机 `.venv` 通过 .pth 读取原 E 盘环境依赖；独立机器应按仓库部署文档安装依赖。浏览器测试运行结束后会关闭测试服务。', '',
        '## B. 真实实验结果', '',
        '保持 44 条非起搏记录、43 个匿名患者组、201/202 合并及 31/6/6 原分区；新增研究只使用 train+val 的 37 组、86,286 拍。5 外层折 × 3 固定种子 × 4 模型，内部拟合/早停/阈值校准/外层评价患者互斥，最大 12 轮。下表为每个种子完整 OOF 指标的均值±种子样本标准差，不是患者置信区间。', '',
        '|模型|Macro-F1|Accuracy|Balanced Accuracy|', '|---|---|---|---|']
    for name in ['A0', 'A1', 'A2', 'A3']:
        rows = [r['pooled'] for r in summary['models'] if r['model'] == name]
        text.append('|'+name+'|'+'|'.join(fmt([r[k] for r in rows]) for k in ['macro_f1', 'accuracy', 'balanced_accuracy'])+'|')
    text += ['', '|模型|类别|Precision|Recall|F1|支持拍数/患者数|', '|---|---|---|---|---|---|']
    for name in ['A0', 'A1', 'A2', 'A3']:
        rows = [r['pooled'] for r in summary['models'] if r['model'] == name]
        for c in summary['classes']:
            metrics = [r['per_class'][c] for r in rows]
            text.append(f'|{name}|{c}|'+'|'.join(fmt([m[k] for m in metrics]) for k in ['precision','recall','f1'])+f"|{metrics[0]['support']}/{metrics[0]['subject_count']}|")
    text += ['', '完整每折、每患者和错误转移分析见 [研究报告](INNOVATION_REPORT.md) 第5–6节及 `rhythm_fusion/results/cv_cpu_v1/summary.json`（含全部三种子）。S 类 50.02% 的支持来自同一患者，F 类 84.38% 来自同一患者；不能将大量心拍当作独立患者。', '',
        '|A2 拒识代理|实际 Coverage|接受拍错误率|拒识拍真实错误率|错误检测 AUROC|', '|---|---|---|---|---|']
    for method in ['max_score', 'entropy']:
        rows = [r for r in selective['results'] if r['model']=='A2' and r['method']==method]
        text.append('|'+method+'|'+'|'.join(fmt([r[k] for r in rows]) for k in ['coverage','accepted_error_rate','rejected_error_rate','error_detection_auroc'])+'|')
    text += ['', '阈值来自每折内部独立校准患者的90%分位数，不保证新患者90%覆盖。逐类接受率、全体/保留分母召回、每患者拒识比例及描述性 Risk–Coverage 扫描均保存在 `uncertainty/results/revalidation_20261119/cv_cpu_v1/summary.json`；与继承结果逐字段完全相同。', '',
        '## C. 当前能成立的结论', '',
        '当前开发患者及短预算内，A2 相对 A0 的 OOF Macro-F1 平均提升 0.1044，三个种子均提升；同容量 A3 未保留收益，支持有效节律对应关系具有信息价值。RR-only 有独立判别力，但整体不及融合。每个种子 30–31/37 患者固定四类F1改善，4–5患者下降，仍存在患者异质性。', '',
        'S 类 Precision/F1 改善，但 Recall 均值下降约0.0453且种子波动明显；F 类 F1 仍仅约0.0357，不能称已解决 S/F 识别困难。不确定性代理对错误有有限排序能力，拒识后全体预测并未变得更准确，不能称为临床风险概率。', '',
        '创新是既有轻量融合方法的可审计实现、受控消融和患者隔离的教学集成；原项目此前已有4维RR＋focal分支，不可主张首次CNN＋RR。波形右侧窗口及双向滤波为离线条件，专家定位不等于端到端异常发现。', '',
        '未执行：新增 N/V 四模型重复、外部数据库/前瞻性验证、临床阈值、概率校准、长预算敏感性、自动QRS误差/真实缺失节律效果实验。网页 N/V 显示空状态。当前适合撰写如实限定的课程扩展章节，不能作独立外部验证或临床有效性主张。原课程论文不变，新增章节草稿见 [PAPER_CHAPTER_DRAFT.md](PAPER_CHAPTER_DRAFT.md)。', '',
        '## D. 本次真实测试与保护', '',
        f"Python：{tests['tests']}项，失败{tests['failures']}，错误{tests['errors']}，跳过{tests['skipped']}；浏览器：{browser['stats']['expected']}通过，失败{browser['stats']['unexpected']}，跳过{browser['stats']['skipped']}。构建与 setup 后 TypeScript 检查退出码0。",
        f"保护清单：{protection['checked_files']}文件，变化{len(protection['changed'])}；所有60个checkpoint权重、scaler、源代码fingerprint、分组和概率已复核。所有86286行RR/掩码对照原始标注重新计算。本次未打开原 test.npz。", '',
        '保留失败证据：初次沙箱内 TestClient 在34项后被本地socket限制挂起并中止，未计通过；本机重跑通过。首次类型检查因副本未生成 .umi 导出失败，执行 Umi setup 后通过。原始失败记录未删除。', '',
        '|本次命令记录|退出码|耗时秒|', '|---|---|---|']
    for p in sorted(validation.glob('revalidation_20261119_*.json')):
        record = json.loads(p.read_text(encoding='utf-8'))
        if 'command' in record:
            text.append(f"|[{p.stem}](validation/{p.name})|{record['exit_code']}|{record['elapsed_seconds']:.2f}|")
    text += ['', '新增图表：`rhythm_fusion/figures/revalidation_20261119/`，13对PNG+SVG及catalog.json；浏览器截图：`validation/revalidation_20261119_browser/screenshots/`；完整权重复算：`validation/revalidation_20261119_artifacts.json`；本次新增文件哈希清单：`REVALIDATION_FILES.csv`。', '',
        '复核命令：`.venv/Scripts/python.exe -B -m research_extensions.revalidate --full`；新Smoke入口 `-m research_extensions.revalidate_smoke`（拒绝覆盖已存在目录）；分析重绘入口 `-m research_extensions.revalidate_analysis`；浏览器命令在web/frontend下为 `node node_modules/@playwright/test/cli.js test --config playwright.revalidation.config.ts`。', '',
        '生成时间：'+datetime.now().astimezone().isoformat()]
    (ROOT / 'research_extensions/REVALIDATION_DELIVERY.md').write_text('\n\n'.join(text[:1])+'\n'+'\n'.join(text[1:])+'\n', encoding='utf-8')
    paths = list((ROOT/'research_extensions').glob('revalidate*.py')) + [ROOT/'research_extensions/delivery_20261119.py', ROOT/'research_extensions/REVALIDATION_DELIVERY.md', ROOT/'research_extensions/rhythm_fusion/src/figures.py', ROOT/'web/frontend/playwright.revalidation.config.ts', ROOT/'web/frontend/tests/rhythm-lab.spec.ts', ROOT/'web/frontend/tests/rhythm-hunter-regression.spec.ts']
    paths += [p for p in validation.rglob('revalidation_20261119*') if p.is_file()]
    paths += [p for p in (validation/'revalidation_20261119_browser').rglob('*') if p.is_file() and p.suffix != '.sqlite3']
    paths += list((ROOT/'research_extensions/rhythm_fusion/figures/revalidation_20261119').glob('*'))
    with (ROOT/'research_extensions/REVALIDATION_FILES.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream); writer.writerow(['path','size','sha256'])
        for p in sorted(set(paths)):
            writer.writerow([p.relative_to(ROOT).as_posix(),p.stat().st_size,sha256(p)])
    print('Generated REVALIDATION_DELIVERY.md and REVALIDATION_FILES.csv')


if __name__ == '__main__':
    main()
