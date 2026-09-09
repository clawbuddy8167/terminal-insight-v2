"""Unit tests for metrics parsers and price bands."""
from __future__ import annotations

from terminal_insight_v2.category.schema import FieldDef
from terminal_insight_v2.metrics.parse import (
    is_dedicated,
    metric_kinds_for_field,
    parse_device_fields,
    parse_mah,
    parse_price,
    parse_watt,
    price_band_cny,
)


def test_parse_price_variants():
    assert parse_price("4499元起") == 4499.0
    assert parse_price("1.2万") == 12000.0
    assert parse_price("¥3,299") == 3299.0
    assert parse_price("无报价") is None


def test_parse_mah_watt_from_long_text():
    text = "5000mAh；100W 有线快充"
    assert parse_mah(text) == 5000.0
    assert parse_watt(text) == 100.0
    assert parse_watt("5G；Wi-Fi 7") is None


def test_price_bands():
    assert price_band_cny(1999) == "入门"
    assert price_band_cny(2999) == "中端"
    assert price_band_cny(4999) == "中高端"
    assert price_band_cny(6999) == "旗舰"
    assert price_band_cny(None) is None


def test_dedicated_column_beats_long_text():
    battery = FieldDef(
        name="电池容量",
        description="电池",
        example="6000mAh",
        data_type="string",
        validators=["mah"],
        key_spec=True,
    )
    power = FieldDef(
        name="功耗与续航管理",
        description="续航叙事",
        example="5000mAh；100W",
        data_type="text",
        validators=["mah", "watt"],
    )
    defs = {"电池容量": battery, "功耗与续航管理": power}
    assert metric_kinds_for_field(battery) == {"mah"}
    assert is_dedicated(battery, "mah")
    assert not is_dedicated(power, "mah")

    rows = [
        {
            "device_id": "phone:a:m1",
            "brand": "A",
            "model": "M1",
            "field_name": "功耗与续航管理",
            "display_text": "5000mAh；80W",
            "policy": "unanimous",
        },
        {
            "device_id": "phone:a:m1",
            "brand": "A",
            "model": "M1",
            "field_name": "电池容量",
            "display_text": "6600mAh",
            "policy": "unanimous",
        },
        {
            "device_id": "phone:a:m1",
            "brand": "A",
            "model": "M1",
            "field_name": "起售价",
            "display_text": "2999元起",
            "policy": "unanimous",
        },
    ]
    price_def = FieldDef(
        name="起售价",
        description="价",
        example="2999元起",
        data_type="price",
        validators=["has_digit"],
    )
    defs["起售价"] = price_def
    dm = parse_device_fields(rows, defs)
    assert dm.get("mah") == 6600.0
    assert dm.values["mah"].source_field == "电池容量"
    assert dm.get("watt") == 80.0
    assert dm.get("price") == 2999.0
    assert dm.price_band == "中端"
