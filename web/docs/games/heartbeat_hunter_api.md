# Heartbeat Hunter API

前缀 `/api/games/heartbeat-hunter`，复用 FastAPI 服务。所有 sample 均为记录内绝对整数采样点，信号为原始 mV。会话令牌相当于本地匿名会话访问凭证。

| 方法 / 路径 | 输入 | 输出与行为 |
|---|---|---|
| GET `/config` | 无 | 三种难度、计分规则、容差、五关数量、已验证关卡总数；无答案 |
| POST `/start` | `player_id: UUID, difficulty, previous_session_id?` | 随机会话、公开元信息、signal 数组、candidate_samples、服务器时间与截止时间 |
| GET `/session/{session_id}` | 随机会话令牌 | 恢复波形、选择、剩余时间、状态；仅 finished 状态含 result |
| POST `/selections` | `session_id, samples: int[]` | 截止前保存合法选择，不判分、不回传类别 |
| POST `/control` | `session_id, action: pause/resume/abandon/speed, speed?: 0.5/1/1.5/2` | 服务端控制后的公开状态；新手可暂停，限时高难度拒绝暂停 |
| POST `/submit` | `session_id, samples: int[]` | 权威评分、专家答案、逐拍匹配与积分事件；幂等 |
| POST `/finish` | 同 submit | submit 的语义别名，可用于到时结算 |
| GET `/leaderboard?player_id={UUID}` | 本地匿名 UUID | 个人最近 20 个已完成关卡和按难度最高单关分；无全站竞争排名 |

开始/恢复公共字段：`session_id, difficulty, round, status, started_at, deadline, server_time, remaining_seconds, record_id, lead_name, sampling_rate, start_sample, end_sample, duration, historical_signal, signal, samples, candidate_samples, total_score, speed, playback_position`。

`candidate_samples` 仅新手非空，包含全部候选位置，无类别；标准/挑战为空。signal 按 1/fs 等间隔，首点为 start_sample，end_sample 不包含在内。内部 level id、答案、V 数量、标签映射不进入未结束会话响应。

结果字段：`correct, incorrect, missed, precision, recall, score, combo_bonus, time_bonus, max_combo, timed_out, elapsed_seconds, completed_at, grade, answers, events`。

answers 元素含 `sample, symbol, label, meaning`。events 含 `sample, reference_sample, distance_samples, correct, delta, combo`，可审计容差和一对一匹配。

错误：404 无效会话；409 已暂停/结束/超时或非法状态转换；422 非整数、位置越界、未回放、非法难度；503 缺少关卡索引或数据不可用。前端提供错误信息和重新加载入口。

默认数据库 `web/runtime/heartbeat_hunter.sqlite3`；`ECG_HUNTER_DATABASE` 可指定测试数据库路径。按本地单个 Uvicorn worker 运行。游戏路由不会调用专家标注或推理 API 预加载答案。现有教学平台仍公开提供专家标注查询，因此本实现不宣称对具有本机数据访问权的使用者提供比赛级防作弊隔离。
