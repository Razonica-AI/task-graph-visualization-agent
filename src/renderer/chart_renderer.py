from __future__ import annotations

import os
from typing import Dict, Any, List
from datetime import datetime

import plotly.graph_objects as go
import plotly.express as px


def render_chart(
    chart_spec: Dict[str, Any],
    data: List[Dict[str, Any]],
    output_path: str | None = None,
) -> go.Figure:
    """
    Render a chart from spec and data using Plotly.
    
    Args:
        chart_spec: The validated chart specification
        data: List of data records (dicts)
        output_path: Optional path to save HTML file (if None, returns figure only)
    
    Returns:
        Plotly Figure object
    """
    chart_type = chart_spec["chart_type"]
    encoding = chart_spec["encoding"]
    # Ensure meta is always a dict - this is where units are stored
    meta = chart_spec.get("meta") or {}
    if not isinstance(meta, dict):
        meta = {}
    
    # Safely extract encoding fields with null checks
    # Handle both dict format {"field": "...", "type": "..."} and string format "field_name"
    x_encoding_raw = encoding.get("x") or {}
    y_encoding_raw = encoding.get("y") or {}
    
    # Convert string encoding to dict format
    if isinstance(x_encoding_raw, str):
        x_encoding = {"field": x_encoding_raw}
    else:
        x_encoding = x_encoding_raw if isinstance(x_encoding_raw, dict) else {}
    
    if isinstance(y_encoding_raw, str):
        y_encoding = {"field": y_encoding_raw}
    else:
        y_encoding = y_encoding_raw if isinstance(y_encoding_raw, dict) else {}
    
    x_field = x_encoding.get("field")
    y_field = y_encoding.get("field")
    
    if not x_field or not y_field:
        raise ValueError(f"Missing required field in encoding: x_field={x_field}, y_field={y_field}")
    
    x_type = x_encoding.get("type", "nominal")
    y_type = y_encoding.get("type", "quantitative")
    
    # Extract data arrays
    x_data = [row[x_field] for row in data]
    y_data = [row[y_field] for row in data]
    
    # Parse dates if temporal
    if x_type == "temporal":
        x_data = [datetime.strptime(str(d), "%Y-%m") if isinstance(d, str) else d for d in x_data]
    
    # Get axis titles with units - prioritize meta over encoding
    # meta should contain the final formatted titles with units
    if meta.get("x_title"):
        x_title = meta["x_title"]
    else:
        x_title = x_encoding.get("title") or x_field.replace("_", " ").title()
    
    if meta.get("y_title"):
        y_title = meta["y_title"]
    else:
        y_title = y_encoding.get("title") or y_field.replace("_", " ").title()
    
    y_units = meta.get("y_units")
    
    # Format Y-axis title with units if available (fallback if meta.y_title not set)
    if y_units and y_units not in y_title:
        # Only add if not already present
        if f"({y_units})" not in y_title:
            y_title = f"{y_title} ({y_units})"
    
    # Create figure based on chart type
    if chart_type == "line":
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=y_data,
                mode="lines+markers",
                name=y_field,
            )
        )
        fig.update_layout(
            xaxis_title=x_title,
            yaxis_title=y_title,
            hovermode="x unified",
        )
    elif chart_type == "bar":
        # Sort by y if specified
        transforms = chart_spec.get("transforms") or {}
        sort_desc = transforms.get("sort", {}).get("y") == "desc"
        if sort_desc:
            sorted_pairs = sorted(zip(x_data, y_data), key=lambda p: p[1], reverse=True)
            x_data, y_data = zip(*sorted_pairs) if sorted_pairs else ([], [])
            x_data, y_data = list(x_data), list(y_data)
        
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=x_data,
                y=y_data,
                name=y_field,
            )
        )
        fig.update_layout(
            xaxis_title=x_title,
            yaxis_title=y_title,
        )
    elif chart_type == "area":
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=y_data,
                mode="lines",
                fill="tozeroy",
                name=y_field,
            )
        )
        fig.update_layout(
            xaxis_title=x_title,
            yaxis_title=y_title,
        )
    elif chart_type == "pie":
        # For pie charts: x = labels (nominal), y = values (quantitative)
        # Sort by y if specified
        transforms = chart_spec.get("transforms") or {}
        sort_desc = transforms.get("sort", {}).get("y") == "desc"
        if sort_desc:
            sorted_pairs = sorted(zip(x_data, y_data), key=lambda p: p[1], reverse=True)
            x_data, y_data = zip(*sorted_pairs) if sorted_pairs else ([], [])
            x_data, y_data = list(x_data), list(y_data)
        
        fig = go.Figure()
        fig.add_trace(
            go.Pie(
                labels=x_data,
                values=y_data,
                name=y_field,
            )
        )
        # Pie charts don't have axes, use title for the chart
        chart_title = meta.get("title") or x_title
        fig.update_layout(
            title=chart_title,
        )
    else:
        raise ValueError(f"Unsupported chart type: {chart_type}")
    
    # Format Y-axis if currency (skip for pie charts as they don't have axes)
    if chart_type != "pie" and y_units in ("USD", "EUR", "GBP", "JPY"):
        fig.update_layout(
            yaxis_tickformat="$,.0f" if y_units == "USD" else f",.0f",
        )
    
    # Save if output path provided
    if output_path:
        fig.write_html(output_path)
    
    return fig

