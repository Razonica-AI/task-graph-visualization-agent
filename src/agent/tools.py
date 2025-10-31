from __future__ import annotations

import json
import time
from functools import wraps
from typing import Dict, Any, Callable

from llama_index.core.tools import FunctionTool
from llama_index.core.llms import ChatMessage

from src.registry.schema_catalog import SchemaCatalog, load_schema_from_file
from src.validator.chart_validator import validate_spec
from src.agent.prompts import (
    SYSTEM_PROMPT,
    build_catalog_summary,
    build_user_prompt,
    build_repair_prompt,
)
from src.renderer.data_loader import (
    extract_data_array,
)
from src.renderer.chart_renderer import render_chart
from src.agent.logging_config import get_logger

# Initialize logger for tools
tool_logger = get_logger("tool")


def log_tool_execution(tool_name: str, agent_name: str | None = None):
    """
    Decorator to log tool execution with telemetry.
    
    Args:
        tool_name: Name of the tool being executed
        agent_name: Optional agent name (can be inferred from tool)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            # Prepare input for logging (sanitize if needed)
            input_data = {
                "args": [str(arg)[:200] for arg in args],  # Truncate long strings
                "kwargs": {k: str(v)[:200] if isinstance(v, str) else v for k, v in kwargs.items()},
            }
            
            # Log tool call start
            tool_logger.info(
                f"Tool execution started: {tool_name}",
                extra={
                    "event_type": "tool.execute",
                    "tool": tool_name,
                    "agent": agent_name,
                    "input": input_data,
                },
            )
            
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                # Prepare output for logging (sanitize if needed)
                output_data = result
                if isinstance(result, str):
                    # Truncate long JSON strings
                    output_data = result[:500] + "..." if len(result) > 500 else result
                elif isinstance(result, dict):
                    # Truncate large dicts
                    output_str = json.dumps(result)[:500]
                    output_data = output_str + "..." if len(output_str) > 500 else output_str
                
                # Log successful tool execution
                tool_logger.info(
                    f"Tool execution completed: {tool_name}",
                    extra={
                        "event_type": "tool.result",
                        "tool": tool_name,
                        "agent": agent_name,
                        "output": str(output_data)[:500],  # Limit size
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                
                return result
                
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                
                # Log tool error
                tool_logger.error(
                    f"Tool execution failed: {tool_name}",
                    exc_info=True,
                    extra={
                        "event_type": "tool.error",
                        "tool": tool_name,
                        "agent": agent_name,
                        "error": str(e),
                        "duration_ms": round(duration_ms, 2),
                    },
                )
                raise
        
        return wrapper
    return decorator


# Utility functions for tool implementations
def _extract_text_from_llm_response(response: Any) -> str:
    """Extract text content from LlamaIndex LLM response."""
    try:
        # Try response.message.content (most common path)
        message = getattr(response, "message", None)
        if message is not None:
            content = getattr(message, "content", None)
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    text = getattr(item, "text", None)
                    if text:
                        parts.append(str(text))
                    elif isinstance(item, dict):
                        parts.append(str(item.get("text", item.get("content", item.get("value", "")))))
                if parts:
                    return "".join(parts)
        
        # Fallback to response.text
        text_attr = getattr(response, "text", None)
        if isinstance(text_attr, str):
            return text_attr
        
        # Final fallback
        return str(response)
    except Exception:
        return str(response)


@log_tool_execution("apply_auto_fixes", "ValidatorAgent")
def apply_auto_fixes(spec: Dict[str, Any], fixes: Dict[str, Any]) -> Dict[str, Any]:
    """Apply auto-fixes to a chart spec."""
    if not fixes:
        return spec
    merged = {**spec}
    if "encoding" in fixes:
        if merged.get("encoding") is None:
            merged["encoding"] = {}
        x_encoding = merged["encoding"].get("x")
        # Ensure x is a dict - if it's a string, convert it to {"field": string}
        if x_encoding is None:
            merged["encoding"]["x"] = {}
        elif isinstance(x_encoding, str):
            merged["encoding"]["x"] = {"field": x_encoding}
        elif not isinstance(x_encoding, dict):
            merged["encoding"]["x"] = {}
        # Now safe to update since we've ensured it's a dict
        merged["encoding"]["x"].update(fixes["encoding"].get("x", {}))
    if "meta" in fixes:
        if merged.get("meta") is None:
            merged["meta"] = {}
        merged["meta"].update(fixes["meta"])
    for k, v in fixes.items():
        if k not in ("encoding", "meta"):
            merged[k] = v
    return merged


# Tool functions - these will be wrapped as FunctionTools
@log_tool_execution("propose_chart_spec", "ProposerAgent")
def propose_chart_spec(query: str, catalog_summary: str, llm) -> Dict[str, Any]:
    """
    Generate a chart specification from a natural language query.
    
    Args:
        query: User's natural language query
        catalog_summary: String summary of available tables and columns
        llm: LlamaIndex LLM instance
    
    Returns:
        Chart specification dictionary
    """
    user_prompt = build_user_prompt(query, catalog_summary)
    
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=user_prompt + "\n\nOutput ONLY valid JSON for chart_spec.")
    ]
    
    try:
        response = llm.chat(messages)
        content = _extract_text_from_llm_response(response).strip()

        # Try to parse JSON from response
        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()

        data = json.loads(content)
        spec = data.get("chart_spec", data)
        return {"chart_spec": spec, "status": "success"}
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Failed to parse JSON: {str(e)}", "raw_response": "unavailable"}
    except Exception as e:
        return {"status": "error", "message": str(e), "raw_response": "unavailable"}


@log_tool_execution("validate_chart_spec", "ValidatorAgent")
def validate_chart_spec_tool(spec: Dict[str, Any], catalog: SchemaCatalog, data_json: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """
    Validate a chart specification against the schema catalog.
    
    Args:
        spec: Chart specification to validate
        catalog: SchemaCatalog instance
        data_json: Optional data JSON for currency hints
    
    Returns:
        Dictionary with validation status, issues, and auto-fixes
    """
    result = validate_spec(catalog, spec, data_json=data_json)
    return {
        "ok": result.ok,
        "issues": [i.__dict__ for i in result.issues],
        "auto_fixes": result.auto_fixes,
    }


@log_tool_execution("repair_chart_spec", "RepairAgent")
def repair_chart_spec(query: str, catalog_summary: str, prev_spec: Dict[str, Any], issues: Dict[str, Any], llm) -> Dict[str, Any]:
    """
    Repair a chart specification based on validation issues.
    
    Args:
        query: Original user query
        catalog_summary: String summary of available tables and columns
        prev_spec: Previous (invalid) chart spec
        issues: Validation issues dictionary
        llm: LlamaIndex LLM instance
    
    Returns:
        Repaired chart specification
    """
    prompt = build_repair_prompt(query, catalog_summary, json.dumps(prev_spec), json.dumps(issues))
    
    messages = [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=prompt + "\n\nOutput ONLY valid JSON for chart_spec.")
    ]
    
    try:
        response = llm.chat(messages)
        content = _extract_text_from_llm_response(response).strip()

        if content.startswith("```json"):
            content = content.replace("```json", "").replace("```", "").strip()
        elif content.startswith("```"):
            content = content.replace("```", "").strip()

        data = json.loads(content)
        spec = data.get("chart_spec", data)
        return {"chart_spec": spec, "status": "success"}
    except json.JSONDecodeError as e:
        return {"status": "error", "message": f"Failed to parse JSON: {str(e)}", "raw_response": "unavailable"}
    except Exception as e:
        return {"status": "error", "message": str(e), "raw_response": "unavailable"}


@log_tool_execution("render_chart", "RendererAgent")
def render_chart_tool(chart_spec: Dict[str, Any], data_array: list, output_path: str) -> Dict[str, Any]:
    """
    Render a validated chart specification into an interactive HTML visualization.
    
    Args:
        chart_spec: Validated chart specification
        data_array: List of data records (dicts)
        output_path: Path to save HTML file
    
    Returns:
        Dictionary with render status and file path
    """
    # Print JSON data sent for charting
    print("\n" + "="*80)
    print("CHART SPECIFICATION JSON:")
    print("="*80)
    print(json.dumps(chart_spec, indent=2))
    print("\n" + "="*80)
    print("DATA ARRAY JSON:")
    print("="*80)
    print(json.dumps(data_array, indent=2))
    print("="*80 + "\n")
    
    try:
        fig = render_chart(chart_spec, data_array, output_path)
        return {"status": "success", "output_path": output_path, "message": "Chart rendered successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def create_tools(llm, catalog: SchemaCatalog, data_json: Dict[str, Any], schema_json_path: str, catalog_summary: str) -> list[FunctionTool]:
    """
    Create FunctionTools for all chart operations.
    
    Args:
        llm: LlamaIndex LLM instance
        catalog: SchemaCatalog instance
        data_json: Loaded data JSON
        schema_json_path: Path to schema file
        catalog_summary: Pre-built catalog summary string
    
    Returns:
        List of FunctionTool instances
    """
    # Propose tool - needs query string
    def propose_tool_fn(query: str) -> str:
        """Generate chart spec from query. Returns JSON string."""
        # Tool execution is already logged by the decorator on propose_chart_spec
        result = propose_chart_spec(query, catalog_summary, llm)
        if result.get("status") == "success":
            return json.dumps(result["chart_spec"])
        else:
            return json.dumps(result)
    
    propose_tool = FunctionTool.from_defaults(
        fn=propose_tool_fn,
        name="propose_chart_spec",
        description="Generate a chart specification from a natural language query. Input: query string. Returns chart spec JSON string. IMPORTANT: After calling this tool, you MUST update the workflow state with chart_spec = <the JSON result from this tool>."
    )
    
    # Validate tool - needs spec dict
    def validate_tool_fn(spec_json: str) -> str:
        """Validate chart spec. Returns JSON string with validation results."""
        try:
            spec = json.loads(spec_json) if isinstance(spec_json, str) else spec_json
            result = validate_chart_spec_tool(spec, catalog, data_json)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"ok": False, "error": str(e)})
    
    validate_tool = FunctionTool.from_defaults(
        fn=validate_tool_fn,
        name="validate_chart_spec",
        description="Validate a chart specification against schema. Input: chart spec JSON string (get from state.chart_spec). Returns validation result JSON string with 'ok' (bool), 'issues' (list), and 'auto_fixes' (dict). IMPORTANT: After calling this tool, you MUST update workflow state with validation_result = <the parsed JSON result>."
    )
    
    # Repair tool
    def repair_tool_fn(query: str, prev_spec_json: str, issues_json: str) -> str:
        """Repair chart spec. Returns JSON string."""
        try:
            prev_spec = json.loads(prev_spec_json) if isinstance(prev_spec_json, str) else prev_spec_json
            issues = json.loads(issues_json) if isinstance(issues_json, str) else issues_json
            result = repair_chart_spec(query, catalog_summary, prev_spec, issues, llm)
            if result.get("status") == "success":
                return json.dumps(result["chart_spec"])
            else:
                return json.dumps(result)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
    
    repair_tool = FunctionTool.from_defaults(
        fn=repair_tool_fn,
        name="repair_chart_spec",
        description="Repair an invalid chart spec based on validation issues. Input: query string (from state.query), prev_spec JSON string (from state.chart_spec), issues JSON string (from state.validation_result.issues). Returns repaired spec JSON string. IMPORTANT: After calling this tool, you MUST update workflow state with chart_spec = <the JSON result from this tool>."
    )
    
    # Apply fixes tool
    def apply_fixes_tool_fn(spec_json: str, fixes_json: str) -> str:
        """Apply auto-fixes. Returns JSON string."""
        try:
            spec = json.loads(spec_json) if isinstance(spec_json, str) else spec_json
            fixes = json.loads(fixes_json) if isinstance(fixes_json, str) else fixes_json
            result = apply_auto_fixes(spec, fixes)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    apply_fixes_tool = FunctionTool.from_defaults(
        fn=apply_fixes_tool_fn,
        name="apply_auto_fixes",
        description="Apply auto-fixes to a chart spec. Input: spec JSON string (from state.chart_spec), fixes JSON string (from validation_result.auto_fixes). Returns fixed spec JSON string. IMPORTANT: After calling this tool, you MUST update workflow state with chart_spec = <the JSON result from this tool>."
    )
    
    # Render tool
    def render_tool_fn(chart_spec_json: str, output_path: str = "chart.html") -> str:
        """Render chart. Returns JSON string with status."""
        try:
            chart_spec = json.loads(chart_spec_json) if isinstance(chart_spec_json, str) else chart_spec_json
            # Extract data array from data_json if available
            data_array = extract_data_array(data_json, chart_spec.get("data_source", ""))
            result = render_chart_tool(chart_spec, data_array, output_path)
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})
    
    render_tool = FunctionTool.from_defaults(
        fn=render_tool_fn,
        name="render_chart",
        description="Render a validated chart spec into HTML visualization. Input: chart spec JSON string (from state.chart_spec), output path string (MUST be taken directly from state.output_path - do not generate a new path, use the exact value from state). Returns render status JSON string with 'status' and 'output_path'. IMPORTANT: Use state.output_path exactly as it is provided. After calling this tool, you MUST update workflow state with render_result = <the parsed JSON result>."
    )
    
    return [propose_tool, validate_tool, repair_tool, apply_fixes_tool, render_tool]
