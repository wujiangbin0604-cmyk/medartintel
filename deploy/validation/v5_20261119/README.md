# V5论文及复核证据发布验证

基线为公开提交8ac19122efab2b25878f24c02eb7b008db3771e3，本次使用独立发布副本整理修改，发布前整合远端307d81c0b8776052b7a18dce8a767866eda468b8中的GitHub下载重试与验收记录。

- V5：humanizer-zh局部编辑29段，39页逐页检查，42条正文目录核验；数字、引文、英文摘要、图表、公式与页边距保持不变，V4文件保留。证据见 `paper/qa/v5/`。
- 更新包回归：初次9项通过；整合下载重试更新后重新生成归档并重跑，11项通过。命令与输出见 `research_extensions/validation/v5_update_package_tests.*` 和 `v5_update_package_tests_integrated.*`。
- 无训练NPZ及node_modules的发布副本：运行清单1307项通过，六模型加载、60研究checkpoint、120个拒识阈值、18组参考预测、真实单拍及游戏API均通过；见 `runtime.json` 和同名前缀日志。测试使用已有Python依赖及隔离游戏数据库。
- 首次验收API通过，包装工具读取中文目录的子进程stdout时出现编码不一致，退出码1。为子进程固定PYTHONIOENCODING和PYTHONUTF8后，完整重跑退出码0。
- 复核记录包含此前副本执行的96项Python和15项浏览器测试；本次沿用相同的运行时应用源码。部署脚本的编码修复由完整运行验收覆盖。

本次完成Windows本机服务验收。服务器执行 `SERVER_UPDATE.md` 中的命令后，部署脚本重建容器并验证API。

本地已生成 `releases/ECG-AI_Server_Update_20261119_V5.zip` 及SHA256文件；归档为生成物，不提交Git。GitHub更新器从已提交快照生成同一运行范围的覆盖包，备份后更新，不覆盖原ECG、原六模型、已有不同研究checkpoint、.env或游戏数据卷。
