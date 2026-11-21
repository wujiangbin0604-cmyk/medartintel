# V6 Linux模型路径修复

2026年11月21日。原V6包中的研究模型注册表使用Windows反斜杠，Linux构建校验和研究单拍推理无法按该路径找到权重。本次让读取端兼容两种分隔符，新注册表统一写为正斜杠。保留全部60个checkpoint、研究指标、患者分区、.env及游戏数据卷。

## 已上传原ZIP的服务器

只需把随附的ecg_v6_linux_fix.py上传到/root，不必重传模型。Windows PowerShell：

```powershell
scp .\ecg_v6_linux_fix.py root@47.83.150.55:/root/
```

服务器执行：

```bash
set +e
set +u
set +o pipefail
python3 -u /root/ecg_v6_linux_fix.py --rebuild 2>&1 | tee /root/ecg-v6-linux-fix.log
printf 'repair_exit=%s\n' "${PIPESTATUS[0]}"
```

脚本优先使用当前项目目录，否则选择/root下最近解压的ecg-ai-v6-*/ecg-ai，先打印PROJECT路径。也可以明确指定：`python3 /root/ecg_v6_linux_fix.py --project /实际项目根目录 --rebuild`。

修复前校验原60个模型SHA-256；备份受影响的源码和清单，再修改五个源码文件及两份清单。备份位于项目根目录的同级ecg-linux-path-backup-*目录，不进入Docker构建上下文。未知本地源码改动会让脚本停止，避免覆盖。重复执行可安全跳过已安装的补丁。

看到PATCH_OK（或PATCH_ALREADY_APPLIED），随后部署脚本完成且repair_exit=0，再访问 http://47.83.150.55:8000/rhythm-lab 。端口沿用现有.env配置。

若失败，保留以下输出供排查：

```bash
tail -n 100 /root/ecg-v6-linux-fix.log
```

## 使用修正后的完整ZIP重新部署

新文件名为ECG-AI_Full_Server_V6_LinuxFix_20261121.zip，校验文件同名加.sha256。将这两个文件上传/root后执行：

```bash
set +e
set +u
set +o pipefail
(
  set -euo pipefail
  cd /root
  sha256sum -c ECG-AI_Full_Server_V6_LinuxFix_20261121.zip.sha256
  ECG_RELEASE_DIR=$(mktemp -d /root/ecg-ai-v6-linuxfix-20261121-XXXXXX)
  python3 -m zipfile -e ECG-AI_Full_Server_V6_LinuxFix_20261121.zip "$ECG_RELEASE_DIR"
  cd "$ECG_RELEASE_DIR/ecg-ai"
  if [ -f /root/ecg-ai/deploy/ubuntu22/.env ]; then
    cp /root/ecg-ai/deploy/ubuntu22/.env deploy/ubuntu22/.env
  fi
  if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
    bash deploy/ubuntu22/install-docker.sh
  fi
  bash deploy/ubuntu22/deploy.sh
  printf '\nPROJECT=%s\n' "$PWD"
) 2>&1 | tee /root/ecg-v6-linuxfix-deploy.log
printf 'deploy_exit=%s\n' "${PIPESTATUS[0]}"
```

若实际旧项目根目录不是/root/ecg-ai，把复制.env的来源改为实际目录。Compose项目名保持ecg-ai并复用原命名游戏卷；不删除旧项目或数据卷。

## 验证范围

原失败已在POSIX路径语义下复现，并在修复后通过。路径与补丁保护及研究接口共12项回归通过；原ZIP解压副本应用修复后，1279个运行文件、60个研究checkpoint、120个阈值、原六模型18条参考预测及真实研究API均通过。本机仍为Windows，Docker镜像构建最终由服务器执行上述命令验证。
