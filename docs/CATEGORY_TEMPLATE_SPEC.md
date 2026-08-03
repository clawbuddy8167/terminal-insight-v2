# 品类 Excel 模板协议（Category Template Spec）

> 状态：Normative  
> 目标：后续新增品类**只提供一个 Excel 工作簿**，无需修改 Python 代码、提示词或数据库 Schema，即可跑通 Collect → Extract → Backfill → Verify → Excel → Vote。

上级文档：[ARCHITECTURE.md](./ARCHITECTURE.md) · [TECHNICAL_DESIGN.md](./TECHNICAL_DESIGN.md)

---

## 1. 强制约束

1. 新品类交付物唯一入口：`category_templates/{category_id}.xlsx`。  
2. 系统启动或运行前**自动发现**模板并编译；编译失败则拒绝运行。  
3. **禁止**在业务代码中硬编码某品类字段列表。  
4. 模板信息不完整时：**字段级错误退出**，不允许静默猜测后继续。  
5. 验收门槛：虚构第四品类仅靠放入 Excel + fixtures 即可完整跑通六阶段（契约测试）。

---

## 2. 工作簿结构

| Sheet 名（固定） | 必填 | 用途 |
|------------------|------|------|
| `品类配置` | 是 | 品类身份、Discovery 文案、区域默认值 |
| `字段定义` | 是 | 字段语义、校验、检索词、冲突策略 |
| `输出模板` | 是 | Excel 输出列顺序与表头展示名 |
| `信源配置` | 否 | 品类特有权威站点与优先级 |
| `示例数据` | 否 | 1～3 行样例，仅用于编译期校验与文档，不进入生产抽取 |

Sheet 名必须精确匹配（允许前后空白，编译时 strip）。不允许用自由命名替代。

---

## 3. Sheet：品类配置

键值表（两列：`键` / `值`），或单行宽表。推荐键值表。

| 键 | 必填 | 说明 | 示例 |
|----|------|------|------|
| `category_id` | 是 | 稳定英文 ID，小写 `[a-z][a-z0-9_]*` | `phone` |
| `label_zh` | 是 | 中文名 | `手机` |
| `label_en` | 否 | 英文名 | `Phone` |
| `template_version` | 是 | 模板语义版本 | `1.0.0` |
| `region_default` | 否 | 默认区域 | `CN` |
| `discovery_product` | 是 | Discovery 用产品词 | `手机` |
| `discovery_extra` | 否 | 额外范围说明 | `含子品牌 Redmi、iQOO` |
| `discovery_prompt_extra` | 否 | 追加提示段落 | … |
| `search_brands` | 否 | 分号分隔品牌列表 | `华为;小米;OPPO` |
| `identity_fields` | 否 | 分号分隔；默认 `品牌;机型;发布时间` | `品牌;机型;发布时间` |
| `official_spec_required_if_exists` | 否 | 默认 `true` | `true` |
| `official_mall_required_if_exists` | 否 | 默认 `true` | `true` |
| `target_source_count` | 否 | 软目标，默认 10 | `10` |

编译规则：

- `category_id` 必须与文件名（不含扩展名）一致。  
- `template_version` 变更且字段集合变化时，生成新 `schema_fingerprint`。

---

## 4. Sheet：字段定义

表头（列名固定；顺序可变；未知列报错）：

| 列名 | 必填 | 说明 |
|------|------|------|
| `field_name` | 是 | 内部字段名，须与输出列一致（中文可） |
| `display_name` | 否 | 展示名；默认等于 `field_name` |
| `description` | 是 | 抽取 / 提示用完整说明 |
| `data_type` | 是 | `string` / `text` / `price` / `date` / `enum` / `boolean` |
| `required` | 是 | `true` / `false` |
| `is_identity` | 是 | 是否身份字段 |
| `key_spec` | 否 | 是否关键规格（影响缺口优先级） |
| `example` | 是 | 至少一个示例值 |
| `search_keywords` | 否 | 补链关键词，分号分隔 |
| `validators` | 否 | 分号分隔的校验器 ID，见 §7 |
| `conflict_policy` | 否 | `multi_claim`（默认）/ `prefer_official` / `prefer_latest` |
| `empty_display` | 否 | 空值展示；默认留空 |
| `notes` | 否 | 给人看的备注 |

约束：

- 至少包含身份字段：默认必须有 `品牌`、`机型`（可通过 `identity_fields` 声明，但两者仍建议保留）。  
- `is_identity=true` 的字段不得作为「仅补链缺口」的唯一目标（身份来自清单）。  
- `description` 与 `example` 为空 → 编译失败。  
- 同一 `field_name` 重复 → 编译失败。

---

## 5. Sheet：输出模板

| 列名 | 必填 | 说明 |
|------|------|------|
| `column_order` | 是 | 从 1 开始的整数 |
| `field_name` | 是 | 必须在「字段定义」中存在 |
| `header` | 否 | Excel 表头；默认 `display_name` 或 `field_name` |
| `width` | 否 | 列宽提示 |
| `wrap` | 否 | `true`/`false` |

规则：

- `字段定义` 中每个非内部字段都应出现在输出模板；缺失 → 警告（可配置为错误）。  
- 输出模板中出现未定义字段 → **错误**。  
- `column_order` 必须唯一且连续建议从 1..N。

---

## 6. Sheet：信源配置（可选）

| 列名 | 必填 | 说明 |
|------|------|------|
| `source_key` | 是 | 稳定键，如 `zol`、`kkj`、`official_spec` |
| `name_zh` | 是 | 展示名 |
| `tier` | 是 | `P0`/`P1`/`P2`/`P3` |
| `source_kind` | 是 | `official_spec`/`official_mall`/`named`/`third_party` |
| `domains` | 是 | 分号分隔域名 |
| `priority` | 是 | 整数，越小越优先 |
| `auto_search` | 否 | 是否自动 site: 补链，默认 `true` |
| `enabled` | 否 | 默认 `true` |

若本 Sheet 缺失：使用系统内置默认信源目录（与 V1 权威列表对齐），再被品类覆盖。

`official_spec` / `official_mall` 的具体品牌域名可放在本表（`source_key` 带品牌后缀）或后续扩展表；首期允许在全局配置中维护品牌域名图，品类表只声明是否启用官方槽位。

---

## 7. 校验器 ID 注册表（系统内置）

模板 `validators` 列只能引用已注册 ID；未知 ID → 编译失败。

| ID | 含义 |
|----|------|
| `non_empty` | 非空 |
| `date_iso` | `YYYY-MM-DD` |
| `has_digit` | 含数字（价格等） |
| `ip_rating` | 含 IP 等级样式 |
| `mah` | 含 mAh |
| `watt` | 含 W |
| `storage_combo` | 含 GB/TB 或 内存+存储 |
| `screen_token` | 尺寸/Hz/OLED 等 |
| `weight_g` | 重量 g/克 |
| `yes_no_zh` | 支持/不支持 等 |

新品类若需新校验器：属于**平台能力扩展**（需发版注册），不属于「只改 Excel」范围。在文档中明确：仅字段集合与文案可通过 Excel 扩展；新校验器 / 新抓取协议仍需平台升级。

> 产品承诺的「只提供 Excel」覆盖：**字段、说明、检索词、输出列、品类文案、信源偏好**。不覆盖实现全新物理校验算法或全新反爬协议。

---

## 8. 编译产物：`category-schema.json`

```json
{
  "schema_version": 1,
  "category_id": "phone",
  "label_zh": "手机",
  "template_version": "1.0.0",
  "fingerprint": "sha256:…",
  "identity_fields": ["品牌", "机型", "发布时间"],
  "discovery": {
    "product": "手机",
    "extra": "…",
    "prompt_extra": "…",
    "search_brands": ["华为", "小米"]
  },
  "fields": [
    {
      "name": "起售价",
      "display_name": "起售价",
      "description": "国内起售价…",
      "data_type": "price",
      "required": false,
      "is_identity": false,
      "key_spec": true,
      "example": "3999元起",
      "search_keywords": ["起售价", "价格", "官方商城"],
      "validators": ["has_digit"],
      "conflict_policy": "multi_claim"
    }
  ],
  "output_columns": [
    {"order": 1, "field_name": "品牌", "header": "品牌"}
  ],
  "sources": [],
  "compiled_at": "ISO-8601"
}
```

`fingerprint` = 对规范化 JSON（去掉 `compiled_at`）做 sha256。运行批次绑定该指纹。

---

## 9. 运行时绑定

| 阶段 | 如何使用 Schema |
|------|-----------------|
| Collect | `discovery_*`、`sources`、`target_source_count`、官方必采开关 |
| Extract | 由 `fields` 动态生成 Pydantic / JSON Schema；`description` 进入 prompt |
| Backfill | `required`/`key_spec` 决定缺口；`search_keywords` 构造查询 |
| Verify | `validators` + `conflict_policy` |
| Excel | `output_columns` |
| Vote | 投影非空规格字段 + 身份字段 |

---

## 10. 首期三个模板内容来源

| 品类 | `category_id` | 字段对齐 |
|------|---------------|----------|
| 手机 | `phone` | V1 `categories/phone.py` / 智能终端模板 |
| 智能手表 | `watch` | V1 `categories/watch.py` |
| 智能眼镜 | `glasses` | V1 `categories/glasses.py` / AI眼镜产品信息 |

实现阶段将上述 Python 配置**导出**为 Excel，之后以 Excel 为唯一编辑入口；Python 内不再保留平行字段表。

---

## 11. 新增品类操作手册

1. 复制 `category_templates/_scaffold.xlsx`（实现时提供）或任一现有模板。  
2. 修改文件名为 `{category_id}.xlsx`。  
3. 填写 `品类配置`、`字段定义`、`输出模板`，按需填 `信源配置`。  
4. 运行：

   ```bash
   python -m terminal_insight_v2.cli category compile --template category_templates/{id}.xlsx
   python -m terminal_insight_v2.cli run --category {id} --stage all
   ```

5. 若报错，根据 Sheet/列/行号修复后重试。  
6. 无需提 PR 改代码（除非需要新 validators 或新抓取能力）。

---

## 12. 编译错误示例（必须可读）

```text
[category-compile] glasses.xlsx 失败：
  - Sheet「字段定义」第 6 行：缺少必填列值 description（field_name=电池续航）
  - Sheet「输出模板」：field_name=防水等级 未在「字段定义」中声明
  - Sheet「品类配置」：category_id=glass 与文件名 glasses 不一致
```

禁止只抛 `ValidationError` 而不指出 Sheet/行。

---

## 13. 契约测试要求

`tests/contract_category_plugin/`：

1. Fixture：`gadget.xlsx`（虚构「智能小配件」品类，含 5～8 个字段）。  
2. 测试：compile 成功 → mock Collect/Extract/Verify/Excel/Vote 管线消费 Schema。  
3. 测试：删除 `description` 列值 → compile 失败且信息含 Sheet 名。  
4. 测试：仓库内业务代码检索不得出现硬编码 `gadget` 字段元组。

该测试是「只提供 Excel 即可新增品类」的持续守卫。
