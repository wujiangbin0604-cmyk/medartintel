# Windows首次安装与GitHub下载运行验收

验收环境为Windows x64、Python 3.12.10。使用新的虚拟环境，`include-system-site-packages = false`，由实际启动器安装固定运行依赖与官方PyTorch CPU wheel；没有复用旧虚拟环境的已安装包。pip复用了官方wheel下载缓存。`pip check`通过，6个正式模型、60个研究checkpoint严格加载通过。

初次将虚拟环境放在较深的下载目录时，安装PyTorch实际出现WinError 206（文件名或扩展名太长）。启动器现为长目录项目选择用户LOCALAPPDATA下的较短隔离环境，也支持-VenvPath显式指定；无需改变Windows注册表或取得管理员权限。覆盖真实PowerShell脚本的路径选择、显式覆盖及超长路径拒绝三项回归通过。

从GitHub main克隆独立副本时，复用了本机相同Git对象以节省流量，并通过--dissociate解除对象依赖。副本不含虚拟环境、node_modules和大型训练NPZ；未携带用户未提交的文件。使用新环境执行的网页和真实API检查结果见[fresh_runtime.json](fresh_runtime.json)。记录中的下载提交对应验收基线，后续启动器与说明修复另行发布。

这些结果覆盖本次Windows环境。首次安装仍需要Python 3.12、足够的磁盘空间，以及PyPI/PyTorch下载站的网络连接；没有将本次结果写成Linux或macOS实机验收。
