from __future__ import annotations

from typing import Dict, Any

from llama_index.core.agent.workflow import FunctionAgent
from llama_index.llms.openai import OpenAI

from src.agent.tools import create_tools
from src.agent.prompts import build_catalog_summary
from src.registry.schema_catalog import SchemaCatalog


def create_specialized_agents(
    llm: OpenAI,
    catalog: SchemaCatalog,
    data_json: Dict[str, Any],
    schema_json_path: str,
) -> Dict[str, FunctionAgent]:
    """
    Create specialized FunctionAgents for AgentWorkflow.
    
    Returns:
        Dictionary mapping agent names to FunctionAgent instances
    """
    catalog_summary = build_catalog_summary(catalog)
    tools = create_tools(llm, catalog, data_json, schema_json_path, catalog_summary)
    
    # Group tools by agent
    propose_tool = next(t for t in tools if t.metadata.name == "propose_chart_spec")
    validate_tool = next(t for t in tools if t.metadata.name == "validate_chart_spec")
    repair_tool = next(t for t in tools if t.metadata.name == "repair_chart_spec")
    apply_fixes_tool = next(t for t in tools if t.metadata.name == "apply_auto_fixes")
    render_tool = next(t for t in tools if t.metadata.name == "render_chart")
    
    # Proposer Agent - generates initial chart spec from query
    proposer_agent = FunctionAgent(
        name="ProposerAgent",
        description="Generates chart specifications from natural language queries. Always hand off to ValidatorAgent after proposing a spec.",
        system_prompt=(
            "You are a chart specification generator. Your role is to:\n"
            "1. Use propose_chart_spec tool with the user's query from workflow state (state.query) to generate a chart specification\n"
            "2. The tool returns a JSON string - parse it and update workflow state with chart_spec: state.chart_spec = parsed_result\n"
            "3. After successfully generating a spec, ALWAYS hand off to ValidatorAgent for validation\n"
            "4. If proposal fails, inform the user and do not hand off\n\n"
            "CRITICAL: You must update the workflow state with the chart_spec after calling propose_chart_spec. The state update is: chart_spec = <parsed JSON from tool result>"
        ),
        llm=llm,
        tools=[propose_tool],
        can_handoff_to=["ValidatorAgent"],
    )
    
    # Validator Agent - validates and applies auto-fixes, decides next step
    validator_agent = FunctionAgent(
        name="ValidatorAgent",
        description="Validates chart specs, applies auto-fixes, and decides whether to render or repair. Hand off to RendererAgent if valid, or RepairAgent if invalid.",
        system_prompt=(
            "You are a chart specification validator. Your role is to:\n"
            "1. Get chart_spec from workflow state (state.chart_spec) - it's a JSON string, parse it first\n"
            "2. Use validate_chart_spec tool with the parsed chart_spec\n"
            "3. Parse the validation result (JSON string) - it contains 'ok', 'issues', and 'auto_fixes'\n"
            "4. If auto_fixes exist, use apply_auto_fixes tool with chart_spec and auto_fixes, then update state.chart_spec with the fixed spec\n"
            "5. After fixing, re-validate the updated spec\n"
            "6. Update workflow state: state.validation_result = <parsed validation result>\n"
            "7. After validation:\n"
            "   - If valid (ok=true): hand off to RendererAgent if rendering is requested (check state.render_requested)\n"
            "   - If invalid (ok=false): hand off to RepairAgent\n\n"
            "CRITICAL: You MUST update state.validation_result with the parsed validation result. Also update state.chart_spec after applying fixes."
        ),
        llm=llm,
        tools=[validate_tool, apply_fixes_tool],
        can_handoff_to=["RendererAgent", "RepairAgent"],
    )
    
    # Repair Agent - fixes invalid specs based on validation issues
    repair_agent = FunctionAgent(
        name="RepairAgent",
        description="Repairs invalid chart specs based on validation feedback. Always hand off back to ValidatorAgent after repair.",
        system_prompt=(
            "You are a chart specification repairer. Your role is to:\n"
            "1. Get from workflow state: state.query, state.chart_spec (parse JSON string), and state.validation_result.issues (parse JSON)\n"
            "2. Use repair_chart_spec tool with: query, chart_spec JSON string, and issues JSON string\n"
            "3. Parse the repair result (JSON string) and update workflow state: state.chart_spec = <repaired spec>\n"
            "4. After repairing, ALWAYS hand off back to ValidatorAgent for re-validation\n\n"
            "CRITICAL: You MUST update state.chart_spec with the repaired chart specification after calling repair_chart_spec."
        ),
        llm=llm,
        tools=[repair_tool],
        can_handoff_to=["ValidatorAgent"],
    )
    
    # Renderer Agent - terminal agent that renders the final chart
    renderer_agent = FunctionAgent(
        name="RendererAgent",
        description="Renders validated chart specs into HTML visualizations. This is the final step in the workflow.",
        system_prompt=(
            "You are a chart renderer. Your role is to:\n"
            "1. Get chart_spec from workflow state (state.chart_spec - parse JSON string if needed)\n"
            "2. Get output_path from workflow state (state.output_path) - use this EXACT value, do NOT generate a new path\n"
            "3. Use render_chart tool with: chart_spec JSON string (from state.chart_spec) and output_path string (from state.output_path - use the exact value, do not modify it)\n"
            "4. Parse the render result (JSON string) and update workflow state: state.render_result = <parsed result>\n"
            "5. After calling render_chart tool (whether it succeeds or fails), you MUST immediately respond with a final message summarizing the result and STOP. Do not call any more tools.\n"
            "6. If rendering succeeds, report: 'Chart rendered successfully to {output_path}. Workflow complete.'\n"
            "7. If rendering fails, report: 'Rendering failed: {error}. Workflow terminated.'\n\n"
            "CRITICAL: You MUST check state.render_result FIRST. If it exists, exit immediately without calling any tools. If it doesn't exist, proceed with rendering. After calling render_chart, terminate immediately - this is the final step."
        ),
        llm=llm,
        tools=[render_tool],
        can_handoff_to=[],  # Terminal agent
    )
    
    return {
        "proposer": proposer_agent,
        "validator": validator_agent,
        "repair": repair_agent,
        "renderer": renderer_agent,
    }

