from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class ColumnSchema:
    name: str
    dtype: str
    unit: Optional[str] = None


@dataclass
class TableSchema:
    table_name: str
    columns: List[ColumnSchema]

    def has_columns(self, required: List[str]) -> bool:
        names = {c.name for c in self.columns}
        return all(col in names for col in required)

    def get_column(self, name: str) -> Optional[ColumnSchema]:
        for c in self.columns:
            if c.name == name:
                return c
        return None


class SchemaCatalog:
    def __init__(self, tables: Dict[str, TableSchema]):
        self.tables = tables

    @staticmethod
    def _infer_unit(field_name: str, dtype: str) -> str | None:
        """Infer unit from field name and dtype."""
        if dtype not in ("float64", "int64", "float32", "int32"):
            return None
        
        field_lower = field_name.lower()
        if any(term in field_lower for term in ["sales", "revenue", "price", "cost", "amount", "value"]):
            return "USD"
        if "count" in field_lower:
            return None  # Count is unitless
        return None

    @staticmethod
    def from_dict(raw: Dict) -> "SchemaCatalog":
        tables: Dict[str, TableSchema] = {}
        for table_name, payload in raw.items():
            cols = []
            for c in payload.get("columns", []):
                col_dict = dict(c)
                # Infer unit if missing
                if "unit" not in col_dict or not col_dict.get("unit"):
                    inferred = SchemaCatalog._infer_unit(col_dict["name"], col_dict["dtype"])
                    if inferred:
                        col_dict["unit"] = inferred
                cols.append(ColumnSchema(**col_dict))
            tables[table_name] = TableSchema(table_name=table_name, columns=cols)
        return SchemaCatalog(tables)

    def list_tables(self) -> List[str]:
        return list(self.tables.keys())

    def get(self, table_name: str) -> Optional[TableSchema]:
        return self.tables.get(table_name)

    def find_table_covering(self, columns: List[str]) -> Optional[TableSchema]:
        for table in self.tables.values():
            if table.has_columns(columns):
                return table
        return None


def load_schema_from_file(schema_json_path: str) -> SchemaCatalog:
    """Load schema catalog from a JSON file."""
    import json
    
    with open(schema_json_path, "r") as f:
        raw = json.load(f)
    return SchemaCatalog.from_dict(raw)
