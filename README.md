# Task: Graph Plotting Agent

## Senior AI Engineer Skill Assessment

### Overview

Build an autonomous graph plotting agent that works **downstream** of the analytics agent. Given analysis results, the agent should intelligently select appropriate visualizations and generate chart specifications consumable by front-end applications.

**Critical**: For data privacy and security, the agent will **NOT** receive actual data values—only file headers (column names and types) and aggregated analysis results.

### Context

This task involves building a visualization agent that works downstream of an analytics system. You'll receive inputs that simulate what an `AutoAnalyticsAgent` would produce.

**What you WILL have:**

- Azure AI Service credentials (`gpt-5-mini` deployment)
- Sample input scenarios (file headers + analysis results)
- This task description with example inputs/outputs
- Full creative freedom to design your solution

**What you will NOT have:**

- Access to the internal bookworm codebase or repository
- Running analytics agents to call
- Internal Django models, databases, or authentication systems

**Note**: You should work with the provided sample inputs or create mock data matching the specified format. There's no need to actually run or integrate with `AutoAnalyticsAgent`—focus on building the visualization intelligence layer.

### Objectives

Build an intelligent agent that:

1. **Understands visualization intent** from natural language queries
2. **Selects appropriate graph types** (line, bar, pie, scatter, etc.) based on data characteristics and query context
3. **Extracts plottable data** from analysis results
4. **Generates complete chart specifications** with titles, axis labels, and units

The agent should work downstream of an analytics system, receiving pre-computed results rather than raw data.

### Technical Requirements

#### Constraints

- **Privacy-first**: Agent receives only file headers (column metadata) and pre-computed analysis results—never raw data
- **Azure AI**: Use provided `gpt-5-mini` deployment for intelligent decision-making
- **Standalone**: Build independently without relying on internal framework code

#### Azure AI Service Configuration

You will be provided with these credentials:

```python
AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
AZURE_OPENAI_API_KEY = "your-api-key"
AZURE_OPENAI_DEPLOYMENT = "gpt-5-mini"
AZURE_OPENAI_API_VERSION = "2024-02-15-preview"
```

#### Sample Input Scenarios

**Scenario 1: Temporal Analysis**

File headers:

```python
{"total_sales_over_time.csv": {"columns": [
    {"name": "month", "dtype": "datetime64[ns]"},
    {"name": "total_sales", "dtype": "float64"},
    {"name": "order_count", "dtype": "int64"}
]}}
```

Analysis results:

```python
{
    "answer": "Sales grew from $45K to $68K over 12 months.",
    "metrics": {
        "monthly_data": [
            {"month": "2024-01", "total_sales": 45000, "order_count": 245},
            {"month": "2024-02", "total_sales": 52000, "order_count": 289},
            {"month": "2024-03", "total_sales": 68000, "order_count": 312}
            # ... 9 more months
        ]
    }
}
```

Query: "Show total sales over time"

Expected output: Line chart with `x_title="Month"`, `y_title="Total Sales"`, `y_units="USD"`

---

**Scenario 2: Category Comparison**

File headers:

```python
{"gross_sales_by_channel.csv": {"columns": [
    {"name": "channel", "dtype": "object"},
    {"name": "gross_revenue", "dtype": "float64"}
]}}
```

Analysis results:

```python
{
    "answer": "Online channel leads with $125K revenue.",
    "metrics": {
        "channel_breakdown": [
            {"channel": "Online", "gross_revenue": 125000},
            {"channel": "Retail", "gross_revenue": 89000},
            {"channel": "Wholesale", "gross_revenue": 45000}
        ]
    }
}
```

Query: "Compare revenue by channel"

Expected output: Bar chart with `x_title="Channel"`, `y_title="Gross Revenue"`, `y_units="USD"`

---

**Scenario 3: Distribution/Pie Chart**

File headers:

```python
{"sessions_by_device.csv": {"columns": [
    {"name": "device_type", "dtype": "object"},
    {"name": "session_count", "dtype": "int64"}
]}}
```

Analysis results:

```python
{
    "answer": "Mobile accounts for 59% of sessions.",
    "metrics": {
        "device_distribution": [
            {"device_type": "Desktop", "session_count": 15420, "percentage": 0.31},
            {"device_type": "Mobile", "session_count": 28934, "percentage": 0.59},
            {"device_type": "Tablet", "session_count": 3421, "percentage": 0.07},
            {"device_type": "Other", "session_count": 892, "percentage": 0.03}
        ]
    }
}
```

Query: "What's the breakdown of sessions by device type?"

Expected output: Pie chart with `title="Session Distribution by Device Type"`, no axes needed

### Evaluation Criteria

- **Correctness**: Produces valid chart specifications that match the output schema
- **Intelligence**: Makes appropriate graph type selections and extracts correct data
- **System Design**: Well-architected solution with clear component separation
- **Code Quality**: Clean, maintainable code with proper error handling

### Deliverables

1. **Working implementation** demonstrating the solution
2. **Examples** showing the agent handling different visualization scenarios
3. **Documentation** explaining your approach and design decisions
4. **Tests** (optional but encouraged)

### Input/Output Specification

#### Inputs to Graph Plotting Agent

```python
# Input 1: User query (natural language)
query = "Show total sales over time"

# Input 2: File headers (column metadata only - NO actual data for privacy)
file_headers = {
    "total_sales_over_time.csv": {
        "columns": [
            {"name": "month", "dtype": "datetime64[ns]"},
            {"name": "total_sales", "dtype": "float64"},
            {"name": "order_count", "dtype": "int64"}
        ]
    }
}

# Input 3: Analysis results from AutoAnalyticsAgent (aggregated/computed values only)
analysis_results = {
    "answer": "Total sales increased from $450K in January to $680K in March, showing a 51% growth over the quarter.",
    "metrics": {
        "monthly_sales": [
            {"month": "2025-01", "total_sales": 450000},
            {"month": "2025-02", "total_sales": 520000},
            {"month": "2025-03", "total_sales": 680000}
        ],
        "total_revenue": 1650000,
        "growth_rate": 0.51
    }
}
```

#### Expected Output Format

```python
{
    "graphs": [
        {
            "graph_type": "line",  # Options: "line", "bar", "scatter", "pie"
            "title": "Total Sales Over Time",
            "x_title": "Month",  # Optional: axis label
            "y_title": "Total Sales",  # Optional: axis label
            "x_units": "month",  # Optional: unit of measurement
            "y_units": "USD",  # Optional: unit of measurement
            "plots": [
                {"x": "2025-01", "y": 450000},
                {"x": "2025-02", "y": 520000},
                {"x": "2025-03", "y": 680000}
            ]
        }
    ]
}
```

#### Sample Usage

```python
agent = PlottingAgent()

result = agent.generate_visualizations(
    query="Show total sales over time",
    file_headers=file_headers,
    analysis_results=analysis_results
)

print(result)
# Output: {"graphs": [...]}
```

### Time Estimate

**4-6 hours** for a senior engineer

### Getting Started

```bash
# Create your project structure
mkdir plotting_agent
cd plotting_agent

# Set up Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install openai pandas python-dotenv pytest

# Create .env file with Azure credentials
cat > .env << EOF
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_DEPLOYMENT=gpt-5-mini
AZURE_OPENAI_API_VERSION=2024-02-15-preview
EOF

# Start development with your chosen architecture
# (file structure is up to you)
```

---

### Summary

Design and build an intelligent visualization agent that transforms analysis results into chart specifications. This is a **system design and implementation challenge**—demonstrate your approach to architecting an AI-powered component that bridges analytics and visualization.

Work with the provided sample inputs or create your own mock data. Focus on demonstrating intelligent graph selection, data extraction, and chart specification generation.

---

**Good luck! We're excited to see your approach to building an intelligent visualization agent.**
