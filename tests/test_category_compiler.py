from pathlib import Path

import pytest

from terminal_insight_v2.category.compiler import CategoryCompileError, compile_template
from terminal_insight_v2.category.writer import fields_to_output, write_category_workbook


def _gadget_spec() -> dict:
    fields = [
        {
            "field_name": "品牌",
            "display_name": "品牌",
            "description": "品牌名",
            "data_type": "string",
            "required": "true",
            "is_identity": "true",
            "key_spec": "false",
            "example": "Acme",
            "search_keywords": "",
            "validators": "",
            "conflict_policy": "multi_claim",
            "empty_display": "",
            "notes": "",
        },
        {
            "field_name": "机型",
            "display_name": "机型",
            "description": "型号",
            "data_type": "string",
            "required": "true",
            "is_identity": "true",
            "key_spec": "false",
            "example": "Gadget One",
            "search_keywords": "",
            "validators": "",
            "conflict_policy": "multi_claim",
            "empty_display": "",
            "notes": "",
        },
        {
            "field_name": "发布时间",
            "display_name": "发布时间",
            "description": "发布日期",
            "data_type": "date",
            "required": "false",
            "is_identity": "true",
            "key_spec": "false",
            "example": "2026-01-01",
            "search_keywords": "发布",
            "validators": "date_iso",
            "conflict_policy": "multi_claim",
            "empty_display": "",
            "notes": "",
        },
        {
            "field_name": "续航",
            "display_name": "续航",
            "description": "电池续航说明",
            "data_type": "text",
            "required": "false",
            "is_identity": "false",
            "key_spec": "true",
            "example": "8小时",
            "search_keywords": "续航;电池",
            "validators": "",
            "conflict_policy": "multi_claim",
            "empty_display": "",
            "notes": "",
        },
    ]
    return {
        "category": {
            "category_id": "gadget",
            "label_zh": "智能小配件",
            "label_en": "gadget",
            "template_version": "1.0.0",
            "discovery_product": "智能小配件",
            "discovery_extra": "契约测试用虚构品类",
            "search_brands": "Acme",
            "identity_fields": "品牌;机型;发布时间",
            "target_source_count": "5",
        },
        "fields": fields,
        "output": fields_to_output(fields),
    }


def test_compile_gadget(tmp_path: Path):
    path = tmp_path / "gadget.xlsx"
    write_category_workbook(path, _gadget_spec())
    schema = compile_template(path, persist=False)
    assert schema.category_id == "gadget"
    assert len(schema.fields) == 4
    assert schema.fingerprint
    assert schema.output_columns[0].field_name == "品牌"


def test_compile_missing_description(tmp_path: Path):
    spec = _gadget_spec()
    spec["fields"][3]["description"] = ""
    path = tmp_path / "gadget.xlsx"
    write_category_workbook(path, spec)
    with pytest.raises(CategoryCompileError) as ei:
        compile_template(path, persist=False)
    msg = str(ei.value)
    assert "字段定义" in msg
    assert "description" in msg
    assert "续航" in msg


def test_compile_unknown_output_field(tmp_path: Path):
    spec = _gadget_spec()
    spec["output"].append(
        {
            "column_order": 99,
            "field_name": "不存在字段",
            "header": "x",
            "width": 10,
            "wrap": "true",
        }
    )
    path = tmp_path / "gadget.xlsx"
    write_category_workbook(path, spec)
    with pytest.raises(CategoryCompileError) as ei:
        compile_template(path, persist=False)
    assert "未在「字段定义」中声明" in str(ei.value)
