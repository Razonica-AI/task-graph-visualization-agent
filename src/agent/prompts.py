from __future__ import annotations

from typing import Dict


SYSTEM_PROMPT = (
    "You are a visualization spec assistant. Produce ONLY a single JSON object named chart_spec "
    "that conforms to the agreed schema: {data_source, chart_type, encoding{x,y,color?,tooltip?}, transforms?, meta?}. "
    "Rules: use only fields that exist in the provided schema catalog; prefer line for temporal trends, bar for categorical comparisons, "
    "pie for proportions/percentages; include axis titles but do not invent units—if unsure, omit and let validator add. No prose."
)


def build_catalog_summary(catalog) -> str:
    lines = ["TABLES:"]
    for table_name in catalog.list_tables():
        table = catalog.get(table_name)
        cols = ", ".join(
            f"{c.name}:{c.dtype}{'[' + c.unit + ']' if getattr(c, 'unit', None) else ''}" for c in table.columns
        )
        lines.append(f"- {table_name}: {cols}")
    return "\n".join(lines)


def build_user_prompt(query: str, catalog_summary: str) -> str:
    return (
        "Task: Given the user query and the schema catalog, output a single chart_spec JSON.\n\n"
        f"User query: {query}\n\n"
        f"Schema catalog:\n{catalog_summary}\n\n"
        "Output policy: JSON only, no markdown, no prose."
    )


def build_repair_prompt(query: str, catalog_summary: str, spec_json: str, issues_json: str) -> str:
    return (
        "Task: The previous chart_spec had validation issues. Revise it to fix ONLY these issues while keeping intent.\n\n"
        f"User query: {query}\n\n"
        f"Schema catalog:\n{catalog_summary}\n\n"
        f"Previous chart_spec JSON:\n{spec_json}\n\n"
        f"Validation issues JSON:\n{issues_json}\n\n"
        "Output policy: JSON only, no markdown, no prose."
    )
