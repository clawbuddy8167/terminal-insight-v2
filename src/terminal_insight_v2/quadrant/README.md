# quadrant — CCC 切片机型四象限图

**职责**：从 `resolved.json` 解析结构量，叠加 Vote 提名，写出本 run 的 `quadrant.json` + `quadrant.html`。

**不变量**：
- 研究层视图，禁止写回事实库。
- 默认轴：价格 × 电池；原点为本窗口落点中位数。
- 图自称 CCC 切片，不假装六套参考系。

**不做**：第七 Stage；LLM 估坐标；把象限标签当事实。
