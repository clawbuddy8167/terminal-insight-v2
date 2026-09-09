#!/usr/bin/env python3
"""Bootstrap phone/watch/glasses Excel templates from V1 field knowledge."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from terminal_insight_v2.category.writer import fields_to_output, write_category_workbook

OUT = ROOT / "category_templates"


def _f(
    name: str,
    desc: str,
    example: str,
    *,
    data_type: str = "text",
    required: bool = False,
    is_identity: bool = False,
    key_spec: bool = False,
    keywords: str = "",
    validators: str = "",
) -> dict:
    return {
        "field_name": name,
        "display_name": name,
        "description": desc,
        "data_type": data_type,
        "required": "true" if required else "false",
        "is_identity": "true" if is_identity else "false",
        "key_spec": "true" if key_spec else "false",
        "example": example,
        "search_keywords": keywords,
        "validators": validators,
        "conflict_policy": "multi_claim",
        "empty_display": "",
        "notes": "",
    }


PHONE_FIELDS = [
    _f("品牌", "厂商品牌", "华为", data_type="string", required=True, is_identity=True),
    _f("机型", "机型全称", "Pura 80 Ultra", data_type="string", required=True, is_identity=True),
    _f("发布时间", "发布会日期 YYYY-MM-DD", "2026-07-01", data_type="date", is_identity=True, validators="date_iso"),
    _f("起售价", "国内起售价，如 4499元起", "4499元起", data_type="price", key_spec=True, keywords="起售价;价格;官方商城", validators="has_digit"),
    _f("电池容量", "电池额定容量，单位 mAh", "5000mAh", data_type="string", key_spec=True, keywords="电池;容量;mAh", validators="mah"),
    _f("充电功率", "有线/无线快充功率，单位 W", "100W", data_type="string", key_spec=True, keywords="快充;充电功率;瓦", validators="watt"),
    _f("防水和防护", "IP等级与机身防护", "IP68", key_spec=True, keywords="防水;IP68;防护", validators="ip_rating"),
    _f("核心算力与存储", "SoC/GPU/RAM/ROM", "骁龙8 Gen3；12GB+256GB", key_spec=True, keywords="处理器;内存;存储", validators="storage_combo"),
    _f("前沿通信能力", "5G/Wi-Fi/蓝牙/NFC等", "5G；Wi-Fi 7；蓝牙5.4；NFC", keywords="5G;Wi-Fi;蓝牙;NFC"),
    _f("屏幕显示技术", "尺寸/分辨率/刷新率/亮度", "6.8英寸 OLED 120Hz", key_spec=True, keywords="屏幕;刷新率;亮度", validators="screen_token"),
    _f("功耗与续航管理", "续航叙事与综合功耗描述（容量与功率以专用列为准）", "长续航；AI 动态功耗", key_spec=False, keywords="电池;续航;快充", validators="mah;watt"),
    _f("声学与音频", "扬声器/麦克风/音频格式", "立体声双扬声器", keywords="扬声器;音频"),
    _f("智能传感与交互", "指纹/传感器/交互", "屏下指纹；陀螺仪", keywords="指纹;传感器"),
    _f("AI底层能力", "端侧AI/大模型/更新承诺", "端侧大模型；四年系统更新", keywords="AI;大模型"),
    _f("核心宣发亮点与差异化功能", "发布会主打卖点", "潜望长焦；卫星通信", keywords="亮点;卖点"),
]

WATCH_FIELDS = [
    _f("品牌", "厂商品牌", "华为", data_type="string", required=True, is_identity=True),
    _f("机型", "机型全称", "WATCH GT 5", data_type="string", required=True, is_identity=True),
    _f("发布时间", "发布日期 YYYY-MM-DD", "2026-07-01", data_type="date", is_identity=True, validators="date_iso"),
    _f("起售价", "起售价", "1488元起", data_type="price", key_spec=True, keywords="价格;起售价", validators="has_digit"),
    _f("表壳尺寸与材质", "尺寸与材质", "46mm 钛金属", key_spec=True, keywords="表壳;尺寸;材质", validators="watch_size"),
    _f("屏幕显示", "屏幕规格", "1.43英寸 AMOLED", keywords="屏幕;AMOLED"),
    _f("续航与充电", "续航与充电", "14天；快充", key_spec=True, keywords="续航;充电", validators="watch_battery"),
    _f("防水等级", "ATM或米级防水", "5ATM", key_spec=True, keywords="防水;ATM", validators="watch_water"),
    _f("传感器与健康", "健康传感器", "心率；血氧；ECG", key_spec=True, keywords="心率;血氧;ECG"),
    _f("系统与连接", "系统与连接", "HarmonyOS；蓝牙；GPS", keywords="系统;蓝牙;GPS"),
    _f("表带与适配", "表带规格", "22mm 氟橡胶", keywords="表带"),
    _f("核心宣发亮点与差异化功能", "亮点", "长续航；玄玑感知系统", keywords="亮点"),
]

GLASSES_FIELDS = [
    _f("品牌", "厂商品牌", "雷鸟", data_type="string", required=True, is_identity=True),
    _f("机型", "产品型号全称", "雷鸟V4", data_type="string", required=True, is_identity=True),
    _f("发布时间", "上市日期 YYYY-MM-DD", "2026-06-01", data_type="date", is_identity=True, validators="date_iso"),
    _f("起售价", "售价/起售价", "3299元", data_type="price", key_spec=True, keywords="价格", validators="has_digit"),
    _f("是否支持拍摄", "拍摄能力", "支持，1200万像素", key_spec=True, keywords="拍摄;摄像头", validators="yes_no_zh"),
    _f("是否支持显示", "显示方案", "双目彩色显示", key_spec=True, keywords="显示;光波导", validators="yes_no_zh"),
    _f("重量", "整机重量", "49g", key_spec=True, keywords="重量", validators="weight_g"),
    _f("续航", "电池与续航", "210mAh，续航4h", key_spec=True, keywords="续航;电池", validators="mah"),
    _f("接入AI大模型", "接入大模型", "通义千问", keywords="大模型;AI"),
    _f("SOC芯片", "主控芯片", "高通AR1", key_spec=True, keywords="SOC;芯片"),
    _f("交互方式", "交互方式", "语音；触控板", keywords="交互;语音;触控"),
    _f("AI应用", "AI应用场景", "翻译；会议纪要；识物", keywords="AI应用;翻译"),
]

DEFAULT_SOURCES = [
    {
        "source_key": "official_spec",
        "name_zh": "官网参数页",
        "tier": "P0",
        "source_kind": "official_spec",
        "domains": "",
        "priority": 1,
        "auto_search": "true",
        "enabled": "true",
    },
    {
        "source_key": "official_mall",
        "name_zh": "官方商城",
        "tier": "P0",
        "source_kind": "official_mall",
        "domains": "",
        "priority": 2,
        "auto_search": "true",
        "enabled": "true",
    },
    {
        "source_key": "zol",
        "name_zh": "中关村在线",
        "tier": "P2",
        "source_kind": "named",
        "domains": "detail.zol.com.cn;zol.com.cn",
        "priority": 20,
        "auto_search": "true",
        "enabled": "true",
    },
    {
        "source_key": "kkj",
        "name_zh": "快科技",
        "tier": "P1",
        "source_kind": "named",
        "domains": "news.mydrivers.com;mydrivers.com",
        "priority": 10,
        "auto_search": "true",
        "enabled": "true",
    },
]


def _cat(cid: str, label: str, product: str, extra: str, brands: str, fields: list) -> dict:
    return {
        "category": {
            "category_id": cid,
            "label_zh": label,
            "label_en": cid,
            "template_version": "1.0.0",
            "region_default": "CN",
            "discovery_product": product,
            "discovery_extra": extra,
            "discovery_prompt_extra": "",
            "search_brands": brands,
            "identity_fields": "品牌;机型;发布时间",
            "official_spec_required_if_exists": "true",
            "official_mall_required_if_exists": "true",
            "target_source_count": "10",
        },
        "fields": fields,
        "output": fields_to_output(fields),
        "sources": DEFAULT_SOURCES,
    }


def main() -> None:
    specs = {
        "phone": _cat(
            "phone",
            "手机",
            "手机",
            "含子品牌 Redmi、iQOO、一加、真我等",
            "华为;荣耀;小米;Redmi;OPPO;一加;vivo;iQOO;三星",
            PHONE_FIELDS,
        ),
        "watch": _cat(
            "watch",
            "手表",
            "智能手表/可穿戴手表",
            "含运动手表、智能手表；排除手环",
            "华为;荣耀;小米;Apple;三星;Garmin;Amazfit;OPPO",
            WATCH_FIELDS,
        ),
        "glasses": _cat(
            "glasses",
            "智能眼镜",
            "AI眼镜/智能眼镜/AR眼镜",
            "含消费级AI眼镜、AR眼镜；排除纯VR头显",
            "Rokid;雷鸟;XREAL;理想;华为;小米;Meta",
            GLASSES_FIELDS,
        ),
    }
    for cid, spec in specs.items():
        out = write_category_workbook(OUT / f"{cid}.xlsx", spec)
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
