# 🌍 GeoThermal Sim Assistant

> An LLM-powered agentic interface for deep geothermal district heating network simulation, built on [pandapipes](https://www.pandapipes.org/) and [LangGraph](https://github.com/langchain-ai/langgraph).

---

## Overview

GeoThermal Sim Assistant bridges the gap between complex thermohydraulic simulations and accessible natural language interaction. Users can query, configure, and compare geothermal district heating network scenarios through a conversational AI agent — without needing to write simulation code directly.

This project is motivated by the challenges of integrating deep geothermal energy into urban heating infrastructure.

---

## Architecture

```
User (Natural Language)
        │
        ▼
┌─────────────────────┐
│   Chainlit UI /     │
│   FastAPI Endpoint  │
└────────┬────────────┘
         │
         ▼
┌───────────────────────────────────────────────────────┐
│        LangGraph Agent                                │
│                                                       │
│  ┌──────────┐  ┌─────────────┐                        │
│  │ LLM Node │→ │ Tool Router │                        │
│  └──────────┘  └──────┬──────┘                        │
│                        │                              │
│         ┌──────────────┼──────────────┐               │
│         ▼              ▼              ▼               │
│  run_simulation  compare_scenarios  explain_concept   │
└───────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────┐
│   pandapipes        │
│   Thermohydraulic   │
│   Simulation Engine │
└─────────────────────┘
```

### Components

| Module | Description |
|--------|-------------|
| `simulation/network.py` | pandapipes network builder & simulation runner |
| `agent/agent.py` | LangGraph agent with 3 simulation tools |
| `api/main.py` | FastAPI REST endpoints (`/chat`, `/simulate`) |
| `app.py` | Chainlit conversational UI |

---

## Network Model

The simulated network represents a simplified **deep geothermal district heating doublet** connected to urban consumers:

```
[Geothermal Doublet]
        │ (hot water, 60–100°C)
        ▼
[Circulation Pump]
        │
        ▼
[Main Supply Pipe]
        │
   ┌────┴───────────────────────────────────────────────┐
   │                                                    │
   │     [Consumer 1] [Consumer 2] ... [Consumer N]      │
   │                                                    │
   └────┬───────────────────────────────────────────────┘
        ▼
[Return Header] → back to geothermal source
```

**Simulated variables:**
- Supply & return temperatures (°C)
- Junction pressures (bar)
- Mass flow rates (kg/s)
- Pipe flow velocities (m/s)
- Total heat output (kW)

---

## Features

- **Natural Language Interface** — Ask questions like *"What happens if I add 2 more consumers?"* and get simulation-backed answers
- **Parametric Simulation** — Configure supply temperature, pipe geometry, number of consumers, mass flow, and pressure
- **Scenario Comparison** — Side-by-side analysis of network configurations (e.g. high-temp vs. low-temp geothermal integration)
- **REST API** — `/simulate` endpoint for direct programmatic access to pandapipes results
- **Agentic Reasoning** — LangGraph agent decides when to run a simulation vs. explain a concept

---

## Evaluation

The `benchmark/` package provides a repeatable evaluation harness for the agent, inspired by **RAGAS-style component-level evaluation** — measuring retrieval (parameter extraction) and generation (simulation correctness) independently rather than relying solely on end-to-end metrics.

### Metrics

| Metric | What it measures | Scoring |
|--------|-----------------|---------|
| **Parameter Extraction Accuracy** | How precisely the agent parses numeric values from natural language prompts and maps them to the correct simulation parameters | Fraction of expected parameters extracted within 1% numeric tolerance |
| **Simulation Correctness Score** | Whether the pandapipes result returned by the agent matches pre-computed ground truth | 1.0 if `total_heat_output_kw` within 2%; 0.5 if within 5%; 0.0 otherwise |
| **Latency** | End-to-end wall-clock time, broken down into pandapipes simulation time vs. estimated LLM round-trip time | Seconds (total / sim / LLM) |

A test case **passes** when both Parameter Extraction and Simulation Correctness reach ≥ 80%.

### Example Results

| Test Case | Prompt (excerpt) | Param % | Sim % | Latency | Status |
|-----------|-----------------|---------|-------|---------|--------|
| tc_001 | Run a simulation with 3 consumers at 90°C supply… | 100% | 100% | 3.2s | PASS |
| tc_002 | What is the heat output with 5 consumers and 0.8 kg/s… | 100% | 100% | 4.1s | PASS |
| tc_003 | Simulate a network with 80°C supply, 50°C return, 1km pipe | 100% | 100% | 3.9s | PASS |
| tc_004 | Compare 90/60°C vs 70/40°C scenarios with 3 consumers | 100% | 100% | 5.1s | PASS |
| tc_005 | Run simulation with 4 consumers, 6 bar, 0.12m diameter | 67% | 50% | 3.5s | FAIL |
| **Average** | — | **87%** | **92%** | **3.2s** | **8/10** |

### Running the Evaluation

```bash
# Run all 10 test cases and save benchmark/eval_report.json
python -m benchmark.evaluator

# Print terminal report and generate benchmark/eval_chart.png
python -m benchmark.report
```

---

## Quick Start

### 1. Clone & install

```bash
git clone https://github.com/<your-username>/geothermal-sim-assistant.git
cd geothermal-sim-assistant
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# groq_api_key is already set in .env.example — copy and confirm
```

### 3. Run the Chainlit UI

```bash
chainlit run app.py
```

Open [http://localhost:8000](http://localhost:8000) in your browser.

### 4. Or run the FastAPI backend

```bash
uvicorn api.main:app --reload
```

API docs at [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Example Interactions

**Simulation query:**
```
User: Run a simulation with 5 consumers at 85°C supply and 55°C return temperature

Agent: Running pandapipes simulation...

Results for your 5-consumer network at 85/55°C:
- Total heat output: 314.5 kW
- Supply pressure: 6.0 bar → Return pressure: 3.8 bar (ΔP = 2.2 bar)
- Mass flow per consumer: 0.5 kg/s (total: 2.5 kg/s)
- Average supply-side pipe velocity: 0.64 m/s

The network operates within normal hydraulic parameters...
```

**Scenario comparison:**
```
User: Compare 90/60°C with 70/40°C — which gives better heat output?

Agent: Running both scenarios...

Scenario A (90/60°C): 376.7 kW  
Scenario B (70/40°C): 251.1 kW  
→ Scenario A delivers 50% more heat output due to the higher ΔT...
```

**Concept question:**
```
User: What is a geothermal doublet?

Agent: A geothermal doublet consists of two boreholes: one production well 
that extracts hot water from deep underground (1–5 km)...
```

---

## Direct API Usage

```python
import requests

# Run a simulation directly
response = requests.post("http://localhost:8000/simulate", json={
    "supply_temp_c": 90,
    "return_temp_c": 60,
    "n_consumers": 4,
    "consumer_mass_flow_kg_s": 0.6,
    "pipe_length_km": 0.8,
    "pipe_diameter_m": 0.12,
    "geothermal_pressure_bar": 7.0
})

result = response.json()
print(f"Heat output: {result['total_heat_output_kw']} kW")
print(f"Pressure drop: {result['pressure_drop_bar']} bar")
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Simulation | [pandapipes](https://pandapipes.org) |
| Agent Framework | [LangGraph](https://github.com/langchain-ai/langgraph) |
| LLM | Groq llama-3.1-8b-instant (via langchain-groq) |
| Backend | FastAPI |
| UI | Chainlit |
| Data | pandas, numpy |

---

## Context

This project explores the integration of LLM-based agentic interfaces
with domain-specific simulation tools — specifically thermohydraulic
modeling of district heating networks. It demonstrates how natural
language interaction can make complex energy system simulations
accessible to planners, engineers, and researchers without requiring
direct programming knowledge.

---

## Author

**Vishva Hirenkumar Jani**  
AI Systems & Backend Engineer  
[linkedin.com/in/vishva-jani](https://linkedin.com/in/vishva-jani)  
Fraunhofer IPK Berlin / Brandenburg University of Technology

---

## License

MIT License — see [LICENSE](LICENSE) for details.
