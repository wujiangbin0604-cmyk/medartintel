# 本地通信限制复现

初次基线和线程限制重试均在 34 个测试完成后进入首个 TestClient 测试挂起，已中止，不能计作通过。使用空 FastAPI 应用复现，8 秒故障栈定位在 Windows socket._fallback_socketpair -> accept -> asyncio ProactorEventLoop 初始化。此时尚未运行任何 ECG 路由或模型。

```powershell
.venv/Scripts/python.exe -B -c "import faulthandler; faulthandler.dump_traceback_later(8,exit=True); from fastapi import FastAPI; from fastapi.testclient import TestClient; a=FastAPI(); a.get('/')(lambda: {'ok':True}); print(TestClient(a).get('/').json())"
```

沙箱内退出码 1（超时主动退出）；沙箱外相同最小应用约 1.9 秒完成，退出码 0，输出 `{'ok': True}`。随后使用自动审批通过的沙箱外执行完成真实本机 API 与浏览器测试。没有修改 FastAPI、anyio、Windows 事件循环实现或依赖版本。

正式通过数只以 all_python_tests.json / pytest.xml 和最终 browser_results.json 为准。首次浏览器 4 通过、1 失败，原因是既有互动页标题的可访问名称含图标名 experiment，测试使用 exact 文本匹配过严；修正定位器后重跑。
