# terminal-insight-v2

证据优先的终端（手机 / 手表 / 眼镜）调研流水线：**采集 → 提取 → 补链 → 校验 → Excel → Vote**。

本目录当前交付为**架构与技术设计基线**（可直接指导开发），实现代码按文档里程碑推进。

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 目标、边界、原则、六阶段职责、Raw/Canonical/Gold、审核语义、信源策略 |
| [docs/TECHNICAL_DESIGN.md](docs/TECHNICAL_DESIGN.md) | 目录、SQLite、阶段接口、抓取降级、状态机、迁移、测试与实现顺序 |
| [docs/CATEGORY_TEMPLATE_SPEC.md](docs/CATEGORY_TEMPLATE_SPEC.md) | **单 Excel 新增品类**的强制协议与编译契约 |

## 已确认决策（摘要）

1. **一个事实库，三层视图**：`raw`（永久原始）/ `canonical`（规范化准事实）/ `gold`（人工审核）；研究索引与报告索引分离。  
2. **对外报告只用 Gold**；不足则留空。  
3. **新品类只提供一个多 Sheet Excel**（品类配置 + 字段定义 + 输出模板 + 可选信源配置），零业务代码修改。  
4. **原始 HTML 永久保存**；动态页降级 JSON / 浏览器 / Markdown-only；失败留痕，不伪造 raw。  
5. **流水线不强制人工闸门**，但保留 `sources.html` 等中间产物；支持锁定字段、拒绝绑定 / 全局拒绝来源、发布 Gold。  
6. **冲突默认并列**：`信源A：说法A；信源B：说法B`。  
7. **补链最多 3 轮**；官网与官方商城存在则必采；每机约 10 源为软目标。

## 与 V1（terminal-insight）关系

- **独立项目**：不在 V1 的 `extracted.json` 上继续叠加。  
- **可复用经验**：品类字段、站点 adapter、URL 机型匹配、豆包检索、Excel/Vote。  
- **不继承**：Infini、RAG 多引擎、全局可变 `out_dir`、单证据主键、Excel 回读 SoT、硬性 5 源上限。

## 快速开始（M1 骨架）

```bash
cd terminal-insight-v2
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

python -m terminal_insight_v2.cli init

# 编译品类模板（新增品类：只放入 category_templates/*.xlsx）
python -m terminal_insight_v2.cli category compile \
  --template category_templates/phone.xlsx

python -m terminal_insight_v2.cli run \
  --category phone --start 2026-07-01 --end 2026-07-31 \
  --stages collect,extract

pytest -q
```

业务阶段（Collect/Extract…）仍为 stub；品类 Excel 编译器已可用。

## 下一步（实现）

按 [TECHNICAL_DESIGN.md §13](docs/TECHNICAL_DESIGN.md) 顺序落地：~~数据底座~~ → ~~品类编译器与三模板~~ → Collect → Extract → Verify → Backfill → Excel/Vote → Review/Gold → V1 迁移与完整契约测试。

## 状态

| 项 | 状态 |
|----|------|
| 架构设计 | 已完成 |
| 技术设计 | 已完成 |
| 品类模板协议 | 已完成 |
| M1 数据底座 | 已完成 |
| M2a 品类编译器 | 已完成（phone/watch/glasses 模板 + gadget 契约测试） |
| M2b Collect+ | 未开始 |
