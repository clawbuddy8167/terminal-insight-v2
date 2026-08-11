"""Category Excel template → compiled schema."""

from .compiler import CategoryCompileError, compile_template
from .loader import list_category_ids, load_category_schema
from .schema import CategorySchema

__all__ = [
    "CategoryCompileError",
    "CategorySchema",
    "compile_template",
    "list_category_ids",
    "load_category_schema",
]
