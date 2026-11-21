# ECG-AI 完整研究版论文 V6

本版以2026年11月19日的自然表达版V5为底稿，将已完成的节律融合与拒识研究纳入全文，另存新版本。

- [Word终稿](paper/final/ECG_AI_课程论文_完整研究版V6.docx)
- [PDF终稿](paper/final/ECG_AI_课程论文_完整研究版V6.pdf)
- [完整Markdown正文](paper/draft/ECG_AI_课程论文_完整研究版V6.md)
- [上传服务器与本地启动指令](UPLOAD_SERVER_V6.md)
- [终稿质量检查](paper/qa/v6/final_quality_check.json)
- [135处数值与真实结果比对](paper/qa/v6/evidence_audit.json)

全文50页，26幅图、25张表、16条参考文献，57项目录链接与页码已核验。七个原有公式仍为可编辑Word公式。新增方法、分组协议、60次训练、逐类与患者结果、独立校准拒识、网页整合、限制及中英文摘要/结论均已写入正文；原V5及既有实验指标保留。

新增开发池为37个患者组、86,286拍，三个种子不是新增患者。A2的OOF Macro-F1为0.4628±0.0230，但S平均Recall下降、F识别仍弱；拒识后的F类全体分母Recall仅0.0047。原测试集没有用于新研究效果确认。本文没有外部或前瞻性临床验证。

修正后的完整上传包名为 `ECG-AI_Full_Server_V6_LinuxFix_20261121.zip`，包含论文、运行数据、原六模型、60个研究模型、前端构建、配置和部署脚本。它不包含首次Docker构建需要联网下载的镜像/依赖，不包含训练NPZ或私人配置。原20261119包已上传到服务器时，可使用[Linux路径修复](SERVER_LINUX_FIX.md)安装小补丁；无需重新上传模型。

如需从完整仓库重新制作同结构的运行包，在Python 3.12环境执行：

```bash
python deploy/ubuntu22/build_release.py --manifest-only
python deploy/build_complete_delivery.py --output-dir releases/v6-rebuilt
```

输出目录中同名ZIP已存在时制作器停止，使用新目录即可。运行验收复用本机已验证的Python 3.12依赖；未将Windows验证写成Ubuntu容器或远程服务器已部署。
