from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from src.registry.schema_catalog import SchemaCatalog, TableSchema


@dataclass
class ValidationIssue:
    code: str
    message: str
    details: Dict[str, Any]


@dataclass
class ValidationResult:
    ok: bool
    issues: List[ValidationIssue]
    auto_fixes: Dict[str, Any]


TEMPORAL_DTYPES = {"datetime64[ns]"}
NUMERIC_DTYPES = {"float64", "int64", "int32", "float32"}
CATEGORICAL_DTYPES = {"object", "string"}


def _get_table(catalog: SchemaCatalog, data_source: str) -> Optional[TableSchema]:
    return catalog.get(data_source)


def validate_spec(catalog: SchemaCatalog, spec_dict: Dict[str, Any], data_json: Dict[str, Any] | None = None) -> ValidationResult:
    issues: List[ValidationIssue] = []
    auto_fixes: Dict[str, Any] = {}

    # Normalize spec to expected shapes from potentially lossy/shorthand LLM outputs
    spec = _normalize_spec(catalog, spec_dict)

    data_source = spec.get("data_source")
    if not data_source:
        issues.append(ValidationIssue("MISSING_FIELD", "Data source is required", {}))
        return ValidationResult(False, issues, auto_fixes)

    table = _get_table(catalog, data_source)
    if not table:
        issues.append(ValidationIssue("TABLE_NOT_FOUND", "Data source not found", {"data_source": data_source}))
        return ValidationResult(False, issues, auto_fixes)

    encoding = spec.get("encoding", {})
    x_encoding = encoding.get("x", {})
    y_encoding = encoding.get("y", {})

    # Check fields exist
    x_field = x_encoding.get("field")
    y_field = y_encoding.get("field")

    if not x_field:
        issues.append(ValidationIssue("FIELD_NOT_FOUND", "X field missing", {}))
    elif not table.get_column(x_field):
        issues.append(ValidationIssue("FIELD_NOT_FOUND", "X field not found in table", {"field": x_field}))
    
    if not y_field:
        issues.append(ValidationIssue("FIELD_NOT_FOUND", "Y field missing", {}))
    elif not table.get_column(y_field):
        issues.append(ValidationIssue("FIELD_NOT_FOUND", "Y field not found in table", {"field": y_field}))

    if issues:
        return ValidationResult(False, issues, auto_fixes)

    x_dtype = table.get_column(x_field).dtype  # type: ignore
    y_dtype = table.get_column(y_field).dtype  # type: ignore

    x_type = x_encoding.get("type")
    y_type = y_encoding.get("type")

    # Dtype compatibility
    if x_type == "temporal" and x_dtype not in TEMPORAL_DTYPES:
        issues.append(ValidationIssue("DTYPE_MISMATCH", "X expects temporal", {"field": x_field, "dtype": x_dtype}))
    if y_type == "quantitative" and y_dtype not in NUMERIC_DTYPES:
        issues.append(ValidationIssue("DTYPE_MISMATCH", "Y expects numeric", {"field": y_field, "dtype": y_dtype}))
    if y_type == "nominal" and y_dtype not in CATEGORICAL_DTYPES:
        issues.append(ValidationIssue("DTYPE_MISMATCH", "Y expects nominal", {"field": y_field, "dtype": y_dtype}))

    # Chart-type intent rules
    chart_type = spec.get("chart_type")
    if chart_type in ("line", "area") and x_type != "temporal":
        issues.append(ValidationIssue("INTENT_RULE", "Line/area must have temporal x", {"chart_type": chart_type}))
    if chart_type == "bar" and x_type == "temporal":
        issues.append(ValidationIssue("INTENT_RULE", "Bar x should be categorical", {}))
    if chart_type == "pie":
        # Pie charts: x should be nominal (labels), y should be quantitative (values)
        if x_type and x_type != "nominal":
            issues.append(ValidationIssue("INTENT_RULE", "Pie chart x (labels) must be nominal/categorical", {"chart_type": chart_type, "x_type": x_type}))
        if y_type and y_type != "quantitative":
            issues.append(ValidationIssue("INTENT_RULE", "Pie chart y (values) must be quantitative", {"chart_type": chart_type, "y_type": y_type}))

    # Units alignment on y
    y_col = table.get_column(y_field)
    y_unit = None
    
    # Priority 1: Use unit from schema column
    if y_col and y_col.unit:
        y_unit = y_col.unit
    # Priority 2: Extract from data JSON answer field if unit missing
    elif data_json:
        from src.renderer.data_loader import extract_currency_from_answer
        y_unit = extract_currency_from_answer(data_json)
    
    if y_unit:
        auto_fixes.setdefault("meta", {})
        axis_title = y_encoding.get("title") or y_field.replace("_", " ").title()
        # Only add unit to title if not already present
        if f"({y_unit})" not in axis_title:
            auto_fixes["meta"]["y_title"] = f"{axis_title} ({y_unit})"
        else:
            auto_fixes["meta"]["y_title"] = axis_title
        auto_fixes["meta"]["y_units"] = y_unit

    # Reasonable defaults
    if chart_type in ("line", "area") and x_encoding.get("time_unit") is None:
        auto_fixes.setdefault("encoding", {})
        auto_fixes["encoding"].setdefault("x", {})
        auto_fixes["encoding"]["x"]["time_unit"] = "yearmonth"

    ok = len(issues) == 0
    return ValidationResult(ok, issues, auto_fixes)


def _infer_type_from_dtype(dtype: Optional[str]) -> Optional[str]:
    if not dtype:
        return None
    if dtype in TEMPORAL_DTYPES:
        return "temporal"
    if dtype in NUMERIC_DTYPES:
        return "quantitative"
    if dtype in CATEGORICAL_DTYPES:
        return "nominal"
    return None


def _normalize_spec(catalog: SchemaCatalog, spec: Dict[str, Any]) -> Dict[str, Any]:
    # Shallow copy to avoid mutating the input
    out: Dict[str, Any] = {**spec}

    # Ensure encoding exists
    encoding = out.get("encoding", {}) or {}

    # Normalize x
    x = encoding.get("x")
    if isinstance(x, str):
        encoding["x"] = {"field": x}
    elif isinstance(x, dict):
        encoding["x"] = x
    else:
        encoding["x"] = {}

    # Normalize y
    y = encoding.get("y")
    if isinstance(y, str):
        encoding["y"] = {"field": y}
    elif isinstance(y, dict):
        encoding["y"] = y
    else:
        encoding["y"] = {}

    # Infer data_source if missing by finding a table that covers x/y fields
    data_source = out.get("data_source")
    x_field = encoding.get("x", {}).get("field")
    y_field = encoding.get("y", {}).get("field")
    if not data_source and x_field and y_field:
        table = catalog.find_table_covering([x_field, y_field])
        if table:
            data_source = table.table_name
            out["data_source"] = data_source

    # Infer types for x/y from catalog dtypes if missing
    table = catalog.get(data_source) if data_source else None
    if table and x_field and "type" not in encoding["x"]:
        x_dtype = table.get_column(x_field).dtype if table.get_column(x_field) else None  # type: ignore
        inferred = _infer_type_from_dtype(x_dtype)
        if inferred:
            encoding["x"]["type"] = inferred
    if table and y_field and "type" not in encoding["y"]:
        y_dtype = table.get_column(y_field).dtype if table.get_column(y_field) else None  # type: ignore
        inferred = _infer_type_from_dtype(y_dtype)
        if inferred:
            encoding["y"]["type"] = inferred

    out["encoding"] = encoding

    # Infer chart_type if missing
    if not out.get("chart_type"):
        x_t = encoding.get("x", {}).get("type")
        if x_t == "temporal":
            out["chart_type"] = "line"
        else:
            out["chart_type"] = "bar"

    return out
