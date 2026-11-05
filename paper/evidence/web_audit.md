# ECG-AI Web 系统证据审计

审计日期：2026-11-05（Asia/Shanghai）。本次为只读源码、机器产物、历史测试日志和已有截图审计；未启动服务、未重新执行软件测试、未重新训练模型。下文“通过”均注明所依据的既有记录，不能理解为本次重新测试。

## 当前实现和论文可用表述

前端实际使用 React、TypeScript、Umi Max、Ant Design、ECharts、Motion。`web/frontend/package.json` 没有把“Ant Design Pro”作为独立直接依赖；当前页面通过自定义 `MedicalLayout` 组织。论文宜写“基于 Umi Max 与 Ant Design 生态构建”，不要把框架品牌或模板名称视为独立实现成果。

后端为 FastAPI，`web/backend/app.py` 定义数据、模型、推理、回放和科研结果 API，并挂载 `heartbeat_hunter` 路由。`web/backend/production.py` 负责同源生产页面；`.umirc.ts` 可核实首页、ECG 工作台、独立 AI 检测入口、实验中心、错误与泛化分析、科研图库、答辩模式、互动实验室、游戏的实际路由。

| 功能 | 实现证据 | 验证证据和界限 |
|---|---|---|
| 真实 ECG 波形、专家心拍和局部详情 | `web/backend/ecg_service.py`；`web/frontend/src/pages/ai-detection/` | `web/docs/visual_fidelity/e2e_final.log` 的真实心拍点击、工作台和三模型回归已通过；信号来自本地 WFDB，非概念图 |
| LR、RF、CNN 真实单心拍及同拍三模型推理 | `web/backend/model_registry.py`；`app.py` 的 `/api/inference/beat`、`compare`、`batch` | 保存验证 CSV 600 条输出一致；当前六模型 SHA-256 与验证 JSON 全部一致 |
| 历史 ECG 回放 | `app.py` 的 `/api/ecg/playback/segment`；前端回放组件 | 第五阶段 16 项全站回归中的回放场景；为预载历史片段回放，不是实时采集监护 |
| 模型实验中心、错误与泛化分析、图库 | `web/backend/research.py`；`app.py` 的科研 API；对应前端页面 | 后端读取已保存结果，`phase4` 和 `visual_fidelity` 原始日志含接口与浏览器检查；不重新计算训练效果 |
| 动画和减少动态效果 | `MedicalLayout.tsx`、`src/utils/motion.tsx`、前端页面和样式 | 第四、第五阶段日志含 reduced-motion、图表和回放联动场景；已有短时性能观测，不是长期压力测试 |
| 心电互动实验室与 Heartbeat Hunter | `.umirc.ts`；`src/pages/interactive-lab/`；`backend/heartbeat_hunter.py` | `games/heartbeat_hunter_testing.md` 记载 2026-11-04 后端 37 passed、游戏 E2E 10 passed；`test-results-hunter/.last-run.json` 为 passed，但不含具体项数 |
| 首次欢迎、教程及游戏至真实 AI 入口 | `components/onboarding/`、`MedicalLayout.tsx`、`tests/welcome-onboarding.spec.ts` | `welcome_onboarding.md` 记载分别运行的 22 场景；`test-results-onboarding/.last-run.json` 为 passed。当前 spec 后续增加普通 HTTP 匿名 ID 场景，不能用旧 22 项数代表当前全套测试项数 |

## 部署路径和训练预处理一致性

1. 用户选择本地真实记录和专家标注采样点；接口使用记录 allowlist，不接收任意文件路径。
2. `ECGStore` 读取 `.hea/.dat/.atr` 和已有划分清单。浏览支持可用记录，模型推理限定纳入实验且具备 MLII 的记录。
3. 对连续信号复用 `src.preprocessing.filters.filter_continuous`；从保存配置读取 0.5–40 Hz、四阶 Butterworth SOS 双向滤波及 5 s 保护区。
4. 按专家标注前 0.3 s、后 0.4 s（含中心点）截取 253 点，拒绝越界、非有限值和不安全窗口。
5. 使用任务对应、由训练集拟合的 `normalization.json`。LR 额外应用保存的 StandardScaler；RF 不附加 scaler；CNN 输入为单通道张量。
6. `ModelRegistry` 只读加载已有工件，核对类别次序、输入维度并计算文件哈希；CNN 以 CPU 和 inference_mode 推理。
7. API 返回类别、逐类概率、模型版本、来源和采样点等信息，前端展示。专家标签用于选拍和回顾性对照，不作为模型输入特征。

推理仍依赖专家标注位置，不是任意未标注 ECG 的自动检测流程。输出概率未经临床校准。

## 600 次一致性核验的独立复算

本次使用标准库直接读取 `web/results/phase2_validation/validation_prediction_comparison.csv` 和 `validation_sample_manifest.csv`，并重算计数与最大误差：

| 项目 | 本次复核值 |
|---|---|
| 验证心拍 | N/V 100 条、N/S/V/F 100 条，共 200 条 |
| 抽样类别 | N/V：N=50、V=50；四分类：N=32、S=25、V=25、F=18 |
| 逐模型比较记录 | 600 条，每任务 300 条 |
| API 类别等于保存预测类别 | 600/600 |
| 最大概率绝对差 | 4.76837158203125e-07 |
| 最大标准化输入绝对差 | 0.0 |
| 当前六个模型工件哈希 | 全部等于 `validation_summary.json` 所记值 |

历史执行日期依据 `web/docs/phase2_model_validation.md` 为 2026-11-02；CSV/JSON本身未保存独立运行时间字段。该过程仅选既有 validation split，机器 JSON 的 `validation_only=true`、`formal_test_data_read=false`。它比较部署路径与历史预测，不能改写为模型分类正确率 100%、外部验证或临床有效性。

## 软件验证证据分层

| 记录 | 原始结果 | 可以说明什么 |
|---|---|---|
| `web/docs/phase4_backend.log` | 18 passed，52 warnings，3.23 s | 2026-11-03 阶段核心与研究扩展接口的历史测试结果 |
| `web/docs/phase4_e2e_final.log` | 15 passed、1 skipped，5.1 min | 开发页面历史交互回归；跳过项不能算通过 |
| `web/docs/phase4_production_e2e.log` | 1 passed，16.7 s | 另行完成的生产构建无外网场景 |
| `web/docs/visual_fidelity/e2e_final.log` | 16 passed，5.2 min | 2026-11-04 第五阶段重构后的全站交互回归 |
| `web/docs/visual_fidelity/typecheck.log`、`build.log` | 既有成功日志 | 历史静态类型检查和生产构建，不是模型性能证据 |
| `web/docs/games/heartbeat_hunter_testing.md` | 37 后端、10 游戏 E2E、62 关卡校验通过的历史记录 | 游戏规则、数据来源及与原工作台联动的既有验证；未发现等价独立完整控制台日志，审计依赖报告和 passed marker 的交叉支持 |
| `web/docs/welcome_onboarding.md` | 原游戏 10、欢迎 11、追加平台回归 1，分别运行共 22 | 文档所描述版本的场景覆盖；现有 spec 后续已新增普通 HTTP ID 场景，项数会变化 |

本次未运行上述命令。`.last-run.json` 只记录 passed 和失败列表，不足以独立恢复具体测试数量、持续时间及被测代码哈希。不要把不同阶段项数相加为“当前总测试通过数”。

## 游戏数据与教学定位

直接读取 `web/backend/game_data/heartbeat_levels.json` 复核为 62 关：beginner 21、standard 21、challenge 20，来源为记录 100、105、106、108、109、114。索引含原始文件哈希、专家标注和采样点；运行波形来自 MLII 真实信号。游戏有选择、计时、服务端匹配评分、复盘及真实三模型入口，SQLite 保存匿名历史。本次未重新执行全部关卡波形校验；历史校验见游戏测试记录。欢迎 SVG 明示“视觉演示·非真实推理结果”，不能当真实 ECG 或推理截图使用。教学功能只需在论文系统章简述，不应替代分类实验分析。

## 推荐正文截图

下表时间来自文件修改时间，与相关测试说明交叉吻合，采用本机 Asia/Shanghai 日期表述；不是 EXIF 或版本哈希证明。均为已有浏览器截图，本次未重新截取。第五阶段早期截图未包含稍后新增的互动入口，应在图题或来源索引注明“2026-11-04 阶段截图”，不要说它们是本次最新运行画面。

| 用途 | 文件 | 像素尺寸 | 保存时间 | 当前性 |
|---|---|---|---|---|
| 首页及新增游戏推荐 | `web/docs/screenshots/welcome_onboarding/dashboard_card_1440x900.png` | 1440×1225 | 2026-11-04 17:01:48 | 包含欢迎版本新增入口；full-page 因纵向内容超过900像素，不可把1440×900当图片实际尺寸 |
| ECG 工作台及真实心拍 | `web/docs/visual_fidelity/iteration2/ecg_1672x941.png` | 1672×941 | 2026-11-04 13:25:21 | 已人工查看，真实波形/选拍/单拍概率；早于互动入口添加 |
| 单心拍真实 AI 推理 | `web/docs/screenshots/welcome_onboarding/real_ai_inference.png` | 1280×1271 | 2026-11-04 17:01:27 | 游戏跳转精确同拍推理的真实测试截图 |
| 三模型对比 | `web/docs/visual_fidelity/iteration2/comparison_1672x941.png` | 1672×941 | 2026-11-04 13:25:23 | 已人工查看，三模型均显示真实同拍结果；早于互动入口添加 |
| 模型实验中心 | `web/docs/visual_fidelity/iteration2/experiments_1672x941.png` | 1672×941 | 2026-11-04 13:25:27 | 第五阶段实验中心实际截图；早于互动入口添加 |

图片源路径全部相对项目根目录。全文使用截图时应复制到 `paper/figures` 并登记。推荐优先用“工作台及三模型对比”一张合并叙述核心流程，避免两张高度相似图片重复占篇幅。

## 依赖声明和运行环境不能混写

`web/frontend/package.json` 声明 React ^18.3.1、Umi Max ^4.4.12、Ant Design ^6.0.0、ECharts ^6.0.0、Motion 14.9.0、TypeScript ^5.7.0、Playwright ^1.56.0。当前 `package-lock.json` 解析出的版本依次为 React 18.3.1、Umi Max 4.7.29、Ant Design 6.6.8、ECharts 6.1.0、Motion 14.9.0、TypeScript 5.9.3、Playwright 1.64.1。这是当前锁文件证据，不能在没有历史快照核对时声称所有旧测试都使用同一版本。

`web/backend/requirements.txt` 只声明 FastAPI>=0.115,<0.120，Uvicorn[standard]>=0.30,<1，httpx>=0.27,<0.29，pytest>=8,<10。根目录 `requirements-lock.txt` 是训练/分析环境依赖快照，不包含 FastAPI/Uvicorn。后端具体安装版需要读取虚拟环境元数据或现场复现，不能直接把版本范围填成历史实际版本。`ModelRegistry` 明确 CPU 推理，可据此写系统模型推理在 CPU 上执行；不得猜测显卡型号。

## 后续论文同步建议

同步检查重点跟踪 `.umirc.ts`、页面与组件、上述模型/推理模块、验证CSV/JSON、包锁文件及已使用PNG。检测变化时只生成提示，不自动改写实验指标。截图若其对应页面源码晚于保存时间，应标为需复查；文件时间差是提示而非画面已经过时的充分证据。若新测试只留下 passed marker，应记录“项数未核验”，不从旧报告补齐。现有本地课程演示不等于长期负载或多用户生产部署验证。
