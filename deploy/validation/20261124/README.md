# Windows首次安装与GitHub下载运行验收

验收环境为Windows x64、Python 3.12.10。新建 `include-system-site-packages = false` 的隔离环境，由启动器安装固定运行依赖与官方PyTorch CPU wheel，pip复用wheel下载缓存。`pip check`、6个正式模型及60个研究checkpoint加载通过。

初次将虚拟环境放在较深的下载目录时，安装PyTorch实际出现WinError 206（文件名或扩展名太长）。启动器现为长目录项目选择用户LOCALAPPDATA下的较短隔离环境，也支持-VenvPath显式指定；无需改变Windows注册表或取得管理员权限。覆盖真实PowerShell脚本的路径选择、显式覆盖及超长路径拒绝三项回归通过。

从GitHub main克隆独立副本时，复用本机相同Git对象以节省流量，通过--dissociate解除对象依赖。副本由Git跟踪文件组成，使用新环境执行网页与API检查，结果见[fresh_runtime.json](fresh_runtime.json)。记录中的下载提交对应验收基线，启动器与说明修复另行发布。

Windows首次安装需要Python 3.12、足够的磁盘空间，以及PyPI/PyTorch下载站的网络连接。
