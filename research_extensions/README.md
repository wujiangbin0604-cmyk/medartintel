# 节律融合与可靠性研究扩展

入口：[`INNOVATION_REPORT.md`](INNOVATION_REPORT.md)、[`PAPER_CHAPTER_DRAFT.md`](PAPER_CHAPTER_DRAFT.md)。不覆盖原正式模型、测试结果或课程论文。

## 复现

在仓库根目录使用现有 `.venv`：

```powershell
.venv/Scripts/python.exe -B -m research_extensions.rhythm_fusion.src.data
.venv/Scripts/python.exe -B -m research_extensions.rhythm_fusion.src.run --smoke
.venv/Scripts/python.exe -B -m research_extensions.rhythm_fusion.src.run
.venv/Scripts/python.exe -B -m research_extensions.rhythm_fusion.src.analyze
.venv/Scripts/python.exe -B -m research_extensions.rhythm_fusion.src.run --config research_extensions/rhythm_fusion/configs/cv_cpu_repeats_v1.json
.venv/Scripts/python.exe -B -m research_extensions.rhythm_fusion.src.analyze --run cv_cpu_repeats_v1
.venv/Scripts/python.exe -B -m research_extensions.rhythm_fusion.src.merge_repeats
.venv/Scripts/python.exe -B -m research_extensions.uncertainty.src.evaluate
.venv/Scripts/python.exe -B -m research_extensions.rhythm_fusion.src.figures
.venv/Scripts/python.exe -B -m research_extensions.protect verify
.venv/Scripts/python.exe -B -m research_extensions.rhythm_fusion.src.report
```

若已完成实验，不应重新构建development.npz（ZIP时间戳会改变文件SHA）；训练入口会识别已有job并校验哈希。源码/数据/配置变化时需要独立实验id，不能混用既有目录。重现数据的数值不等于ZIP容器逐字节一致。训练可自动使用CUDA，正式本轮运行设备为CPU；更换设备需新实验目录。

## 工程入口

- `rhythm_fusion/src/data.py`：完整专家beat事件、过去RR、掩码、逐拍追溯、训练侧scaler。
- `rhythm_fusion/src/models.py`：RRMLP / RhythmMorphologyCNN，保留原HeartbeatCNN不变。
- `rhythm_fusion/src/run.py`：内部拟合/早停/校准＋外层评价、4模型、独立工件保存/识别完成状态。
- `rhythm_fusion/results/*/fold*/seed*/A*/best.pt`：实际模型与scaler、配置；同job的predictions.npz保存外层及内部校准概率。
- `rhythm_fusion/results/cv_cpu_v1/model_registry.json`：每个患者所属外层模型、seed、checkpoint路径/SHA；重复种子原组件目录保持可追溯。
- `uncertainty/src/evaluate.py`：两种代理、校准患者分位阈值、Risk–Coverage与逐类/逐患者分母。
- `web/backend/rhythm_lab.py`：独立只读路由与工件验证；`/api/rhythm/summary`、`/samples?label=S`、`/beat?record_id=100&annotation_sample=2044`。
- `web/frontend/src/pages/rhythm-lab/`：现有Umi/React/AntD/ECharts科研页面；路径 `/rhythm-lab`。
- Hunter 在专家答案区域新增带精确记录/样本位置的链接，不修改评分/存档/计时逻辑。

使用既有 `start-local.ps1` 或 `web.backend.production:app` 启动平台。新增页面与生产dist均已构建；既有8080等端口约定以原部署文档为准，研究测试使用8142。

## 验证

`validation/*.json` 保存命令、工作目录、退出码，`.txt`保存输出；`pytest.xml`、`browser_results.json`及`screenshots/`保存实际测试结果。Windows沙箱本地socket pair限制的最小复现与处理见`validation/sandbox_diagnosis.md`。正式服务/浏览器测试在自动批准的沙箱外本机执行，不修改依赖或事件循环。

`protection_manifest.json`记录开始时1042个原工件SHA及Git状态；`protection_verification.json`是研究交付时的复验。原先未提交的论文文件及Umi appData保留，原论文未覆盖。GitHub发布与服务器更新入口见根目录 [SERVER_UPDATE.md](../SERVER_UPDATE.md)。

`initial_git_status.json`保留首次写入前观察到的Git状态；`runtime_versions.json`记录实际科学计算/服务依赖版本；`DELIVERED_FILES.csv`列出新增及修改交付工件、大小和SHA。磁盘空间中断与只清理本次追踪缓存后的续跑见 `validation/storage_recovery.md`。完整原游戏浏览器断言以仅重定向输出路径的副本执行，来源SHA保存在 `validation/hunter_test_provenance.json`。
