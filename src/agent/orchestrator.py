from __future__ import annotations

import os
import json
import time
import uuid
from typing import Dict, Any

from dotenv import load_dotenv
from llama_index.llms.openai import OpenAI
from llama_index.core.agent.workflow import AgentWorkflow

from src.agent.agents import create_specialized_agents
from src.registry.schema_catalog import load_schema_from_file
from src.renderer.data_loader import (
    get_data_json_path_from_schema,
    load_data_json,
)
from src.agent.logging_config import get_logger

# Initialize logger for workflow
workflow_logger = get_logger("workflow")
agent_logger = get_logger("agent")


def _parse_json_or_keep(value: Any) -> Any:
    """Parse JSON string to dict/list if possible, otherwise return as-is."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def load_env() -> None:
    load_dotenv()


def get_llm() -> OpenAI:
    """Get LlamaIndex OpenAI LLM instance."""
    load_env()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set in environment/.env")
    return OpenAI(model="gpt-4o-mini", api_key=api_key)


class ChartOrchestrator:
    """
    Agent-based orchestrator for chart generation workflow using LlamaIndex AgentWorkflow.
    Uses specialized agents (Proposer, Validator, Repair, Renderer) that intelligently
    coordinate through handoffs without hard-coded logic.
    """

    def __init__(self, schema_json_path: str):
        self.schema_json_path = schema_json_path
        self.catalog = load_schema_from_file(schema_json_path)
        self.data_json_path = get_data_json_path_from_schema(schema_json_path)
        self.data_json = load_data_json(self.data_json_path)
        self.llm = get_llm()
        
        # Create specialized agents
        agents = create_specialized_agents(
            self.llm, 
            self.catalog, 
            self.data_json, 
            self.schema_json_path
        )
        
        # Create workflow with ProposerAgent as root
        self.workflow = AgentWorkflow(
            agents=[agents["proposer"], agents["validator"], agents["repair"], agents["renderer"]],
            root_agent=agents["proposer"].name,
            initial_state={}
        )
    
    async def run(self, query: str, render: bool = True, output_path: str = "chart.html") -> Dict[str, Any]:
        """
        Execute the chart generation workflow using AgentWorkflow.
        
        Agents intelligently decide the flow:
        - ProposerAgent generates initial spec and hands off to ValidatorAgent
        - ValidatorAgent validates, applies fixes, and decides to render or repair
        - RepairAgent fixes issues and hands back to ValidatorAgent
        - RendererAgent renders the final chart
        
        Returns:
            Dictionary with workflow results, matching the original format for compatibility
        """
        workflow_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # Log workflow start
            workflow_logger.info(
                "Workflow execution started",
                extra={
                    "event_type": "workflow.start",
                    "workflow_id": workflow_id,
                    "query": query,
                    "render_requested": render,
                    "output_path": output_path,
                    "schema_path": self.schema_json_path,
                },
            )
            
            # Initialize workflow state
            initial_state = {
                "query": query,
                "chart_spec": None,
                "validation_result": None,
                "auto_fixes": None,
                "render_requested": render,
                "output_path": output_path,
                "render_result": None,
                "status": "pending",
                "workflow_id": workflow_id,  # Add workflow ID to state for tracking
            }
            
            # Run workflow with user query as initial message
            workflow_response = await self.workflow.run(
                user_msg=query,
                initial_state=initial_state
            )
            
            # Extract final state from workflow
            final_state = workflow_response.get("state", initial_state)
            
            # Log full workflow response for debugging
            workflow_logger.debug(
                "Workflow response structure",
                extra={
                    "event_type": "workflow.response",
                    "workflow_id": workflow_id,
                    "response_keys": list(workflow_response.keys()) if isinstance(workflow_response, dict) else [],
                    "response_type": type(workflow_response).__name__,
                },
            )
            
            # Log state snapshot (debug level for detailed tracking)
            workflow_logger.info(
                "Workflow state snapshot",
                extra={
                    "event_type": "workflow.state",
                    "workflow_id": workflow_id,
                    "state_keys": list(final_state.keys()),
                    "has_chart_spec": final_state.get("chart_spec") is not None,
                    "has_validation": final_state.get("validation_result") is not None,
                    "has_render_result": final_state.get("render_result") is not None,
                    "chart_spec_type": type(final_state.get("chart_spec")).__name__ if final_state.get("chart_spec") is not None else None,
                    "validation_result_type": type(final_state.get("validation_result")).__name__ if final_state.get("validation_result") is not None else None,
                },
            )
            
            # Parse JSON strings from state (agents may store tool outputs as JSON strings)
            chart_spec = _parse_json_or_keep(final_state.get("chart_spec"))
            validation_result = _parse_json_or_keep(final_state.get("validation_result")) or {}
            render_result = _parse_json_or_keep(final_state.get("render_result")) or {}
            
            # Map workflow state to original result format for backward compatibility
            is_valid = validation_result.get("ok", False) if validation_result else False
            duration_ms = (time.time() - start_time) * 1000
            
            result: Dict[str, Any] = {
                "ok": is_valid,
                "query": query,
                "validated": is_valid,
                "validation": validation_result,
                "chart_spec": chart_spec,
            }
            
            # Add render result if available
            if render_result:
                result["render"] = render_result
                if render_result.get("status") == "success":
                    result["output_path"] = output_path
            
            # Log workflow completion
            workflow_logger.info(
                "Workflow execution completed",
                extra={
                    "event_type": "workflow.end",
                    "workflow_id": workflow_id,
                    "success": is_valid,
                    "validated": is_valid,
                    "rendered": bool(render_result),
                    "duration_ms": round(duration_ms, 2),
                    "has_chart_spec": chart_spec is not None,
                },
            )
            
            return result

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Log workflow error
            workflow_logger.error(
                "Workflow execution failed",
                exc_info=True,
                extra={
                    "event_type": "workflow.error",
                    "workflow_id": workflow_id,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                    "query": query,
                },
            )
            
            return {"ok": False, "error": str(e), "message": "Workflow failed", "query": query}
