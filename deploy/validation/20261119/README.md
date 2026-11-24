# 2026-11-19 GitHub发布与本地运行验证

运行来源为Git暂存区导出的独立目录，不复制源工作区被Git忽略的训练NPZ、`.venv`或`node_modules`。复用制作机已验证的Python 3.12科学计算环境，在独立目录启动 `deploy/local.py`，项目模块路径确认为导出目录，随后执行真实HTTP自检。

实际通过：

- Python核心、研究、API及部署回归最终 **107项通过**，见 `python_tests.txt`、`pytest.xml`；包含网络连接和HTTP正文中断两项重试回归。
- 完整性清单 **1278个运行文件**，无Git漏带文件；48条原始记录、62个游戏关卡。
- 原六模型加载，**18条参考预测及概率吻合**。
- 60个正式研究checkpoint逐一严格加载并核对SHA；3种子、60组结果、24组可靠性结果、120份患者隔离阈值。
- 独立目录真实波形、三模型对比、游戏、163张图库及科研实验室接口通过；同一真实心拍调用两个研究模型并返回实际预测。
- 105项中包含GitHub更新器、原模型保护、新研究权重安装、更新前缺失依赖拦截和隔离Python直接运行校验脚本的回归。
- 官方PyPI和PyTorch CPU索引重新核对63项固定依赖，Linux Python 3.12 wheel及依赖闭包可用，记录在 `deploy/ubuntu22/linux_dependency_check.json`。

具体数值见 `staged_checkout.json`。首次导出验证发现校验脚本直接执行时未将项目根加入sys.path，已修复并补充隔离Python回归，初次失败保存在 `initial_cli_import_failure.txt`。

前端沿用研究阶段的生产构建和15项浏览器记录，路径 `research_extensions/validation/`。原1042个保护工件SHA在发布前复验一致。

独立目录测试在Windows上复用制作机Python依赖完成。服务器运行 `deploy.sh` 构建镜像、等待健康检查并执行API验收；首次启动所需依赖由启动器从固定官方索引安装。

服务器命令：[SERVER_UPDATE.md](../../../SERVER_UPDATE.md)。发布后从GitHub实际clone的附加检查记录由 `deploy/validate_git_checkout.py` 生成。

## 发布后的远端文件验收

发布代码提交 `8ac19122efab2b25878f24c02eb7b008db3771e3` 后，从GitHub官方地址获取文件。该次Git clone出现early EOF，官方ZIP在传输后段断开，随后按下述方式恢复下载。

从已下载ZIP中恢复1686个CRC正确的条目，并从同一提交的官方raw地址补齐163个运行文件，之后全部1278个运行文件通过SHA-256验证。在独立系统临时目录启动服务，原六模型18条参考预测、60研究checkpoint、120阈值、真实波形/游戏/图库/科研实验室均通过；详见 `remote_download_recovery.json` 和 `github_download.json`。

恢复下载后完成GitHub发布内容的运行验收。更新器支持两次网络自动重试，下载与校验通过后开始复制项目文件。后续提交增加该重试机制、回归测试、验收记录和文件索引，沿用相同的网页与模型工件。
