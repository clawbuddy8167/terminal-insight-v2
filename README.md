# terminal-insight-v2

证据优先的终端（手机 / 手表 / 眼镜）调研流水线：**采集 → 提取 → 补链 → 校验 → Excel → Vote**。

本目录交付可运行的六阶段流水线与本地 GUI：窗口发现或定向机型采集，产出带信源的 Excel 与六参考系「亮点投票」。

## 文档索引

| 文档 | 内容 |
|------|------|
| [docs/客户交接说明.md](docs/客户交接说明.md) | **客户交付交接**：交付物、环境、配置、操作流程、部署注意 |
| [docs/GUI用户使用手册.md](docs/GUI用户使用手册.md) / [PDF](docs/GUI用户使用手册.pdf) | **GUI 图文手册（浅色，main 默认）** |
| [docs/GUI用户使用手册-深色版.md](docs/GUI用户使用手册-深色版.md) / [PDF](docs/GUI用户使用手册-深色版.pdf) | **GUI 图文手册（深色主题）** |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 目标、边界、原则、六阶段职责、Raw/Canonical/Gold、审核语义、信源策略 |
| [docs/TECHNICAL_DESIGN.md](docs/TECHNICAL_DESIGN.md) | 目录、SQLite、阶段接口、抓取降级、状态机、迁移、测试与实现顺序 |
| [docs/CATEGORY_TEMPLATE_SPEC.md](docs/CATEGORY_TEMPLATE_SPEC.md) | **单 Excel 新增品类**的强制协议与编译契约 |
| [PACKAGING.md](PACKAGING.md) | Windows / macOS 打包与分发 |

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
pip install -e ".[dev,gui]"
cp .env.example .env

python -m terminal_insight_v2.cli init

# 编译品类模板（新增品类：只放入 category_templates/*.xlsx）
python -m terminal_insight_v2.cli category compile \
  --template category_templates/phone.xlsx

python -m terminal_insight_v2.cli run \
  --category glasses --start 2026-01-01 --end 2026-07-31 \
  --stages collect,extract

# 本地桌面 GUI（配置 / 窗口发现或定向机型 / 浏览 runs 与覆盖率）
python run_gui.py
# 或: python -m terminal_insight_v2.gui
# 或: python -m terminal_insight_v2.cli gui

# Windows / macOS 打包：见 PACKAGING.md
# pip install -e ".[packaging]" && pyinstaller build.spec --noconfirm

pytest -q
```

Collect 阶段会：按日期窗发现机型，或使用 GUI 确认的定向清单（`targets.json`）→ 规划 URL → HTTP/Jina 抓取 → 写入 `data/memory/blobs/` 与 `llm-wiki/raw/`，并在 run 目录生成 `sources.html` / `collection_manifest.json`。

Extract 之后会补链、校验、出 Excel，再按六套参考系写「亮点投票」。定向采集目前只在 GUI 提供；CLI `run` 仍走窗口发现。

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
| M2b Collect+ | **MVP 已实现**（discover + fetch + blobs + llm-wiki/raw + sources.html） |
| M2c Extract | **MVP 已实现**（一源一 LLM 调用 → field_assertions + assertions.jsonl） |
| M2d Verify + Excel | **MVP 已实现**（identity/evidence → Resolution → xlsx） |
| Vote | **已实现**（六参考系 → `votes.json` + Excel「亮点投票」） |
| 定向采集 | **已实现**（GUI 粘贴品牌+型号，跳过窗口发现） |
| GUI（PyWebView） | **MVP 已实现**（配置 / 定向 / 跑阶段 / 中途进度 / runs / 覆盖率） |
