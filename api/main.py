"""
FastAPI backend for GeoThermal Sim Assistant.
Exposes chat and simulation endpoints.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import json

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from agent.agent import create_agent

load_dotenv()
from simulation.network import build_district_heating_network, run_simulation

app = FastAPI(
    title="GeoThermal Sim Assistant API",
    description="LangGraph agent for deep geothermal district heating simulation",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Initialize agent ──
GROQ_API_KEY = os.getenv("groq_api_key")
agent = create_agent(groq_api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# ── Schemas ──

class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []

class SimulationRequest(BaseModel):
    supply_temp_c: float = 90.0
    return_temp_c: float = 60.0
    n_consumers: int = 3
    consumer_mass_flow_kg_s: float = 0.5
    pipe_length_km: float = 0.5
    pipe_diameter_m: float = 0.1
    geothermal_pressure_bar: float = 6.0


# ── Routes ──

@app.get("/")
def root():
    return {
        "name": "GeoThermal Sim Assistant",
        "description": "AI-powered district heating network simulation",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "agent_ready": agent is not None,
        "pandapipes": _check_pandapipes(),
    }


@app.post("/chat")
def chat(request: ChatRequest):
    """
    Send a message to the GeoSim agent.
    The agent will run pandapipes simulations as needed and
    return a natural language explanation of results.
    """
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Agent not initialized. Set groq_api_key environment variable."
        )

    from langchain_core.messages import HumanMessage, AIMessage

    # Build message history
    messages = []
    for msg in (request.history or []):
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        else:
            messages.append(AIMessage(content=msg.content))
    messages.append(HumanMessage(content=request.message))

    # Run agent
    result = agent.invoke({
        "messages": messages,
        "simulation_results": [],
        "current_params": {},
    })

    # Extract final response
    final_message = result["messages"][-1]
    sim_results = result.get("simulation_results", [])

    return {
        "response": final_message.content,
        "simulation_results": sim_results,
        "tools_called": [r["tool"] for r in sim_results],
    }


@app.post("/simulate")
def simulate(request: SimulationRequest):
    """
    Directly run a pandapipes simulation with given parameters.
    Returns raw thermohydraulic results without LLM interpretation.
    """
    net = build_district_heating_network(
        supply_temp_k=request.supply_temp_c + 273.15,
        return_temp_k=request.return_temp_c + 273.15,
        geothermal_pressure_bar=request.geothermal_pressure_bar,
        consumer_mass_flow=request.consumer_mass_flow_kg_s,
        n_consumers=request.n_consumers,
        pipe_length_km=request.pipe_length_km,
        pipe_diameter_m=request.pipe_diameter_m,
    )
    result = run_simulation(net)

    if result.status != "converged":
        raise HTTPException(status_code=500, detail=f"Simulation failed: {result.status}")

    return {
        "status": result.status,
        "supply_temperature_c": result.supply_temp_c,
        "return_temperature_c": result.return_temp_c,
        "delta_t_c": round(result.supply_temp_c - result.return_temp_c, 2),
        "total_mass_flow_kg_s": result.mass_flow_kg_s,
        "supply_pressure_bar": result.pressure_supply_bar,
        "return_pressure_bar": result.pressure_return_bar,
        "pressure_drop_bar": round(result.pressure_supply_bar - result.pressure_return_bar, 3),
        "total_heat_output_kw": result.total_heat_output_kw,
        "network_efficiency_pct": result.network_efficiency_pct,
        "junction_temperatures_c": result.junction_temperatures,
        "junction_pressures_bar": result.junction_pressures,
        "parameters": request.dict(),
    }


def _check_pandapipes():
    try:
        import pandapipes
        return pandapipes.__version__
    except ImportError:
        return "not installed"


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
