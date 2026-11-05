# 第三阶段真实截图审查

截图来自 Playwright + Chrome 打开的真实本地页面，目录 `web/docs/screenshots/phase3/`。测试要求真实页面标题出现、API 加载完成后再截图，不以网络空闲或空骨架作为验收。

## 发现与修复

1. 原项目只有工作台，顶部菜单不可点击：增加真实路由与统一平台导航。
2. Umi 自动布局与显式父路由叠加：首轮截图发现双导航、双页脚，已去掉重复父布局，增加导航数量断言。
3. 首屏骨架被过早截图：增加真实标题和语义内容等待条件，重拍总览。
4. 原 8–11px 文字难以投影阅读：提升到 12–14px，页标题 28px、图标题 16–18px。
5. 中央波形被侧栏挤压：1550px 以下右详情改 Drawer，波形使用更宽空间、真实单位和时间。
6. 导航状态深色背景对比不足：增加特定颜色规则；禁用动作按钮取消不合适的蓝底。
7. 图库长页请求过多：每页 12 张，保持图片比例，提供完整大图、报告与下载。
8. 生产构建压缩辅助代码冲突：按本地构建器提示启用 esbuildMinifyIIFE，通过后续构建。

## 自动审查

逐页检查 body.scrollWidth、主要面板右边界、图表实际尺寸、pageerror、HTTP >=400 资源。`phase3_browser_1366.json` / `1440.json` / `1920.json` 为最终截图检查数据；异常注入测试与正常页面资源检查分开。表格在自身容器内滚动属于预期，不应撑宽 body。

## 截图索引

另有 [真实标注点击与 Tooltip](screenshots/phase3/waveform_real_marker_tooltip.png)，由生产环境真实信号生成；八步答辩截图命名为 `demo_step1_1280x720.png` 至 `demo_step8_1280x720.png`。

- [dashboard_1366x768.png](screenshots/phase3/dashboard_1366x768.png)
- [ai-detection_1366x768.png](screenshots/phase3/ai-detection_1366x768.png)
- [comparison_1366x768.png](screenshots/phase3/comparison_1366x768.png)
- [experiments_1366x768.png](screenshots/phase3/experiments_1366x768.png)
- [experiments_nsvf_1366x768.png](screenshots/phase3/experiments_nsvf_1366x768.png)
- [generalization_1366x768.png](screenshots/phase3/generalization_1366x768.png)
- [gallery_1366x768.png](screenshots/phase3/gallery_1366x768.png)
- [dashboard_1440x900.png](screenshots/phase3/dashboard_1440x900.png)
- [ai-detection_1440x900.png](screenshots/phase3/ai-detection_1440x900.png)
- [comparison_1440x900.png](screenshots/phase3/comparison_1440x900.png)
- [experiments_1440x900.png](screenshots/phase3/experiments_1440x900.png)
- [experiments_nsvf_1440x900.png](screenshots/phase3/experiments_nsvf_1440x900.png)
- [generalization_1440x900.png](screenshots/phase3/generalization_1440x900.png)
- [gallery_1440x900.png](screenshots/phase3/gallery_1440x900.png)
- [dashboard_1920x1080.png](screenshots/phase3/dashboard_1920x1080.png)
- [ai-detection_1920x1080.png](screenshots/phase3/ai-detection_1920x1080.png)
- [comparison_1920x1080.png](screenshots/phase3/comparison_1920x1080.png)
- [experiments_1920x1080.png](screenshots/phase3/experiments_1920x1080.png)
- [experiments_nsvf_1920x1080.png](screenshots/phase3/experiments_nsvf_1920x1080.png)
- [generalization_1920x1080.png](screenshots/phase3/generalization_1920x1080.png)
- [gallery_1920x1080.png](screenshots/phase3/gallery_1920x1080.png)

## 人工图像审查

使用图像查看工具检查真实截图及各分辨率审查拼图（contact_*.png），核对导航唯一、卡片边界、文字对比、波形面积、矩阵标签和图像完整比例。截图不是页面实现；所有页面均为真实 React 组件与接口。

## 保留的限制

长页面需要纵向滚动；1366×768 无法在一个首屏同时显示波形、三模型表格和全部明细。科研原图使用各自已有配色与原始文字，未重画或修改已有研究图像。本轮不新增深色主题。
