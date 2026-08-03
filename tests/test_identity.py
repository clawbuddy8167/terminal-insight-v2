from terminal_insight_v2.identity import (
    brand_norm,
    device_id,
    model_norm,
    normalize_url,
    source_id,
)


def test_device_id_stable():
    a = device_id("phone", "华为", "Pura 80 Ultra")
    b = device_id("phone", "huawei", "Pura 80 Ultra 12+512GB")
    assert a.startswith("phone:")
    assert a == b


def test_brand_alias():
    assert brand_norm("红米") == brand_norm("Redmi")


def test_model_strips_storage():
    assert model_norm("Note 17 Pro 8+256GB") == model_norm("Note 17 Pro")


def test_normalize_url_strips_utm():
    u = normalize_url("https://Example.com/path/?utm_source=x&id=1")
    assert u == "https://example.com/path?id=1"
    assert source_id(u) is not None
