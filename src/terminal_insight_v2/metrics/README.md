# metrics — display_text → comparable quantities

**职责**：按品类 Schema 的 `data_type` / `validators`，把 `resolved.json` 里的展示字符串解析为可比较的数（价格、mAh、W、g），并派生价位带标签。

**不变量**：
- 不写回 `resolved.json` / facts.db / Gold。
- 禁止硬编码品类字段名清单；专用列（单一 validator）优先于长文本多指标字段。
- 价位带是研究视图规则，不是事实字段。

**不做**：四象限布局；LLM 估档；AI 能力分级。
