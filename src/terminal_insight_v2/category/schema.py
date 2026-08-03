"""Compiled category schema models."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

DataType = Literal["string", "text", "price", "date", "enum", "boolean"]
ConflictPolicy = Literal["multi_claim", "prefer_official", "prefer_latest"]
Tier = Literal["P0", "P1", "P2", "P3"]


class FieldDef(BaseModel):
    name: str
    display_name: str = ""
    description: str
    data_type: DataType = "text"
    required: bool = False
    is_identity: bool = False
    key_spec: bool = False
    example: str
    search_keywords: List[str] = Field(default_factory=list)
    validators: List[str] = Field(default_factory=list)
    conflict_policy: ConflictPolicy = "multi_claim"
    empty_display: str = ""
    notes: str = ""

    def model_post_init(self, __context: Any) -> None:
        if not self.display_name:
            self.display_name = self.name


class OutputColumn(BaseModel):
    order: int
    field_name: str
    header: str = ""
    width: Optional[int] = None
    wrap: bool = True


class SourceDef(BaseModel):
    source_key: str
    name_zh: str
    tier: Tier
    source_kind: str
    domains: List[str] = Field(default_factory=list)
    priority: int = 100
    auto_search: bool = True
    enabled: bool = True


class DiscoveryConfig(BaseModel):
    product: str
    extra: str = ""
    prompt_extra: str = ""
    search_brands: List[str] = Field(default_factory=list)


class CategorySchema(BaseModel):
    schema_version: int = 1
    category_id: str
    label_zh: str
    label_en: str = ""
    template_version: str
    fingerprint: str = ""
    region_default: str = "CN"
    identity_fields: List[str] = Field(
        default_factory=lambda: ["品牌", "机型", "发布时间"]
    )
    official_spec_required_if_exists: bool = True
    official_mall_required_if_exists: bool = True
    target_source_count: int = 10
    discovery: DiscoveryConfig
    fields: List[FieldDef]
    output_columns: List[OutputColumn]
    sources: List[SourceDef] = Field(default_factory=list)
    compiled_at: str = ""
    template_path: str = ""

    def field_names(self) -> List[str]:
        return [f.name for f in self.fields]

    def spec_fields(self) -> List[FieldDef]:
        ident = set(self.identity_fields)
        return [f for f in self.fields if f.name not in ident]

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Dict used for fingerprint (exclude compiled_at / template_path / fingerprint)."""
        data = self.model_dump()
        for k in ("compiled_at", "template_path", "fingerprint"):
            data.pop(k, None)
        return data

    def dumps(self) -> str:
        return json.dumps(self.model_dump(), ensure_ascii=False, indent=2)
