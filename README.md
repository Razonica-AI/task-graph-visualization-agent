# NL Query to Chart Spec Orchestrator (Agentic AI)

This project turns a natural-language query and schema JSON files into validated chart visualizations using **agentic AI** with LlamaIndex. It uses specialized agents (Proposer, Validator, Repair, Render) coordinated by an OrchestratorAgent that intelligently decides the workflow, rather than hard-coded logic.

## Setup

1. Python 3.10+
2. Create a virtualenv and install dependencies:

```bash
pip install -r requirements.txt
```

3. Environment

- Create a `.env` file with:

```
OPENAI_API_KEY=sk-...
```

## Run

```bash
python -m src.main "Show total sales over time" --schema total_sales_over_time_schema.json
```

or

```bash
python -m src.main "Compare revenue by channel" --schema gross_sales_by_channel_schema.json --output channel_chart.html
```

## Architecture (Agentic AI with LlamaIndex)

- **Schema Loader**: Reads schema JSON files (defines table structure, auto-infers units from field names)
- **OrchestratorAgent**: Coordinates specialized agents using LlamaIndex's OrchestratorAgent pattern
  - **ProposerAgent**: Generates chart specifications from natural language queries
  - **ValidatorAgent**: Validates specs and applies guardrails/auto-fixes
  - **RepairAgent**: Repairs invalid specs based on validation feedback
  - **RendererAgent**: Renders validated specs into interactive visualizations
- **FunctionTools**: All operations exposed as FunctionTools for agent tool calling
- **Deterministic Validator**: Checks schema alignment, dtype compatibility, intent rules, and units
- **Data Loader**: Extracts data arrays from JSON metrics structures and currency from answer fields
- **Chart Renderer**: Converts chart_spec to Plotly visualizations with proper axis titles, units, and formatting

### Agentic Flow

The orchestrator agent intelligently decides:
1. When to call ProposerAgent for spec generation
2. When to validate and apply auto-fixes
3. When repair is needed based on validation issues
4. When to render the final chart
All orchestrated by LLM reasoning, not hard-coded logic.

## Notes

- Schema JSON files should have the data JSON filename as the top-level key
- Units are auto-inferred from field names (sales/revenue → USD) if not specified in schema
- Charts are rendered as interactive HTML files by default
- Use `--no-render` to skip rendering and only get the spec JSON
