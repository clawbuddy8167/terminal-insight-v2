"""Prompt templates for discovery."""
from __future__ import annotations

from terminal_insight_v2.category.schema import CategorySchema


def discovery_system(schema: CategorySchema) -> str:
    product = schema.discovery.product
    extra = schema.discovery.extra or ""
    prompt_extra = schema.discovery.prompt_extra or ""
    return f"""你是{schema.label_zh}产品调研助手。根据检索摘要，抽取窗口期内正式发布的{product}机型清单。
要求：
1. 只保留有明确品牌+型号的正式发布产品；排除传闻/预热。
2. {extra}
3. {prompt_extra}
4. release_date 用 YYYY-MM-DD；不确定可留空字符串。
5. 输出 JSON：{{"devices":[{{"brand":"...","model":"...","release_date":"...","category":"{schema.category_id}"}}]}}
6. 穷尽语料中的明确型号，不要只保留代表性 1 条。"""


def discovery_user(
    schema: CategorySchema,
    date_start: str,
    date_end: str,
    context: str,
) -> str:
    return f"""时间窗口：{date_start} ~ {date_end}
品类：{schema.label_zh}（{schema.discovery.product}）

### 检索摘要 ###
{context}

请输出 devices JSON。"""


def extract_snapshot_system(schema_label: str, field_lines: str) -> str:
    return f"""你是{schema_label}参数抽取助手。根据【单篇页面正文】，抽取目标机型的字段值。
规则：
1. 只依据正文证据；无法从正文支持的字段不要输出。
2. 每个字段最多 1 条；value 用中文简洁填写。
3. snippet 必须摘录支撑 value 的原文短句（30~200字），不得编造。
4. 不要合并多个信源；本篇没有的就留空。
5. 输出 JSON：{{"fields":[{{"name":"字段名","value":"...","snippet":"..."}}]}}；字符串内不要换行。

待抽取字段：
{field_lines}"""


def extract_snapshot_user(brand: str, model: str, url: str, body: str) -> str:
    trimmed = body.strip()
    if len(trimmed) > 14000:
        trimmed = trimmed[:14000] + "\n\n…(正文已截断)"
    return f"""目标机型：{brand} {model}
页面 URL：{url}

### 页面正文 ###
{trimmed}

请输出 fields JSON；无证据的字段不要出现在列表中。"""
