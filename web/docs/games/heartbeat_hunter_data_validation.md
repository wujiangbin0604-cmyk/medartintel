# 真实数据与关卡校验

2026-11-04 实际执行：

```powershell
.\.venv\Scripts\python.exe -m web.backend.build_heartbeat_levels
.\.venv\Scripts\python.exe -m web.backend.build_heartbeat_levels --check
```

结果：62 个有效关卡，新手 21、标准 21、挑战 20。实际记录编号为 100、105、106、108、109、114；均来自本地 `data/mitdb` 中真实 `.dat/.hea/.atr`，采样率 360 Hz，使用 MLII 导联。

数据来源：[PhysioNet MIT-BIH Arrhythmia Database 1.0.0](https://physionet.org/content/mitdb/1.0.0/)。专家原始符号语义见 [PhysioNet annotation documentation](https://physionet.org/static/lightwave/doc/annotations.html)。AAMI 分组复用项目 `src/labels.py::AAMI_MAP`：V/E→V，N/L/R/e/j→N；不得将 N 组统称为所有正常心拍。

## 自动生成与核验

索引位于后端私有 `web/backend/game_data/heartbeat_levels.json`，不会拷入前端 dist。生成程序从完整文件发现真实记录和 V 标注，围绕实际标注搜索窗口，非人工编造时间。一次构建后普通开始游戏只查索引，不扫描整个数据库。服务端原始波形查询复用 ECGStore.window 和既有有界记录缓存。

每关检查：

1. WFDB 文件齐全；复用 load_record 检查头信息、信号 shape、数字通道 checksum、采样率、标注范围和顺序。
2. 记录的真实 MLII 和 mV，360 Hz；窗口位于记录范围且在连续滤波 safe mask 内。
3. 原始信号非空、全为有限值且不是平直窗；没有重采样、归一化或手绘替代。
4. 专家心拍数量 6–60，至少一个 V，V 比例不高于 65%。
5. 全部心拍仅 N/V。S/F/Q、unknown、unmapped_beat 导致整段排除；不会被默认为 N。
6. 排除信号质量改变、伪迹和扑动/颤动标记 `~ | [ ] !`；额外检查片段前的质量和扑动状态，避免窗口落入此前开始的噪声/扑动区间。节律等非心拍标记不作为候选心拍。
7. 标注 sample 唯一；每拍前 0.3 s、后 0.4 s 观察范围完整，避免边界不可判定心拍。
8. 每个原始 symbol 与 AAMI_MAP 一致，答案严格对应实际标注 sample。
9. manifest 保存所有源 hea/dat/atr 的 SHA-256；`--check` 复核文件哈希与全部 62 个窗口。
10. 后端测试将 start 返回的完整 signal 与真实 WFDB 物理信号逐点比较，而非只检查非空。

原始训练模型、processed 数据和实验结果没有被此功能修改。索引中的文件哈希和答案用于后端校验，前端只收到按规则允许的公开字段。
