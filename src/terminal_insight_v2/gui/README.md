# gui — 本地桌面壳（MVP）

**职责**：把流水线配置、启动与 run 产物浏览暴露给 PyWebView UI。

**不变量**：
- 不实现 collect/extract/… 业务逻辑；只调用 `orchestrator.run_pipeline` 与 store/category。
- 流水线在后台线程运行；UI 通过 `get_progress` 轮询。

**不做**：Discovery 链接闸门、Gold 审核、Chat、中途取消（V2 orchestrator 尚无 cancel）。
