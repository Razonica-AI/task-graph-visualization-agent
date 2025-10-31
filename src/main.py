from __future__ import annotations

import argparse
import asyncio
import json

from src.agent.orchestrator import ChartOrchestrator


async def main() -> None:
    parser = argparse.ArgumentParser(description="Chart Spec Orchestrator (Agentic AI)")
    parser.add_argument("query", type=str, help="Natural language query")
    parser.add_argument("--schema", type=str, required=True, help="Path to schema JSON file")
    parser.add_argument("--output", type=str, default="chart.html", help="Output path for chart HTML file")
    parser.add_argument("--no-render", action="store_true", help="Skip chart rendering, only return spec")
    args = parser.parse_args()

    orch = ChartOrchestrator(args.schema)
    result = await orch.run(args.query, render=not args.no_render, output_path=args.output)
    # print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
