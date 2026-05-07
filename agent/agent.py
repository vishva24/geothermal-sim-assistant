"""
LangGraph-based agentic pipeline for the GeoThermal Sim Assistant.
The agent can: run simulations, change parameters, compare scenarios,
and explain results in natural language.
"""

from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import tool
from langchain_groq import ChatGroq
from typing import TypedDict, Annotated, List
import operator
import json

from simulation.network import build_district_heating_network, run_simulation, SimulationResult


# ─────────────────────────────────────────────
# Agent State
# ─────────────────────────────────────────────

class AgentState(TypedDict):
    messages: Annotated[List, operator.add]
    simulation_results: List[dict]
    current_params: dict


# ─────────────────────────────────────────────
# Simulation Tools
# ─────────────────────────────────────────────

@tool
def run_heating_network_simulation(
    supply_temp_c: float = 90.0,
    return_temp_c: float = 60.0,
    n_consumers: int = 3,
    consumer_mass_flow_kg_s: float = 0.5,
    pipe_length_km: float = 0.5,
    pipe_diameter_m: float = 0.1,
    geothermal_pressure_bar: float = 6.0,
) -> str:
    """
    Run a district heating network simulation with the given parameters.
    Returns thermohydraulic results including temperatures, pressures,
    mass flows, and total heat output.

    Args:
        supply_temp_c: Supply temperature in Celsius (default 90°C)
        return_temp_c: Return temperature in Celsius (default 60°C)
        n_consumers: Number of heat consumers / buildings (default 3)
        consumer_mass_flow_kg_s: Mass flow per consumer in kg/s (default 0.5)
        pipe_length_km: Length of distribution pipes in km (default 0.5)
        pipe_diameter_m: Pipe diameter in meters (default 0.1)
        geothermal_pressure_bar: Geothermal source pressure in bar (default 6.0)
    """
    net = build_district_heating_network(
        supply_temp_k=supply_temp_c + 273.15,
        return_temp_k=return_temp_c + 273.15,
        geothermal_pressure_bar=geothermal_pressure_bar,
        consumer_mass_flow=consumer_mass_flow_kg_s,
        n_consumers=n_consumers,
        pipe_length_km=pipe_length_km,
        pipe_diameter_m=pipe_diameter_m,
    )
    result = run_simulation(net)

    output = {
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
        "parameters_used": {
            "supply_temp_c": supply_temp_c,
            "return_temp_c": return_temp_c,
            "n_consumers": n_consumers,
            "consumer_mass_flow_kg_s": consumer_mass_flow_kg_s,
            "pipe_length_km": pipe_length_km,
            "pipe_diameter_m": pipe_diameter_m,
        }
    }
    return json.dumps(output, indent=2)


@tool
def compare_scenarios(
    scenario_a_supply_temp_c: float = 90.0,
    scenario_a_return_temp_c: float = 60.0,
    scenario_b_supply_temp_c: float = 75.0,
    scenario_b_return_temp_c: float = 45.0,
    n_consumers: int = 3,
    consumer_mass_flow_kg_s: float = 0.5,
) -> str:
    """
    Compare two district heating scenarios side by side.
    Useful for analyzing the effect of different temperature levels
    (e.g. high-temp vs low-temp geothermal integration).

    Args:
        scenario_a_supply_temp_c: Supply temperature for scenario A in Celsius
        scenario_a_return_temp_c: Return temperature for scenario A in Celsius
        scenario_b_supply_temp_c: Supply temperature for scenario B in Celsius
        scenario_b_return_temp_c: Return temperature for scenario B in Celsius
        n_consumers: Number of consumers (same for both scenarios)
        consumer_mass_flow_kg_s: Mass flow per consumer in kg/s
    """
    # Run both scenarios
    net_a = build_district_heating_network(
        supply_temp_k=scenario_a_supply_temp_c + 273.15,
        return_temp_k=scenario_a_return_temp_c + 273.15,
        consumer_mass_flow=consumer_mass_flow_kg_s,
        n_consumers=n_consumers,
    )
    result_a = run_simulation(net_a)

    net_b = build_district_heating_network(
        supply_temp_k=scenario_b_supply_temp_c + 273.15,
        return_temp_k=scenario_b_return_temp_c + 273.15,
        consumer_mass_flow=consumer_mass_flow_kg_s,
        n_consumers=n_consumers,
    )
    result_b = run_simulation(net_b)

    heat_diff = result_a.total_heat_output_kw - result_b.total_heat_output_kw
    better = "A" if result_a.total_heat_output_kw >= result_b.total_heat_output_kw else "B"

    comparison = {
        "scenario_A": {
            "label": f"High-Temp ({scenario_a_supply_temp_c}°C / {scenario_a_return_temp_c}°C)",
            "heat_output_kw": result_a.total_heat_output_kw,
            "supply_temp_c": result_a.supply_temp_c,
            "return_temp_c": result_a.return_temp_c,
            "mass_flow_kg_s": result_a.mass_flow_kg_s,
            "pressure_drop_bar": round(result_a.pressure_supply_bar - result_a.pressure_return_bar, 3),
            "status": result_a.status,
        },
        "scenario_B": {
            "label": f"Low-Temp ({scenario_b_supply_temp_c}°C / {scenario_b_return_temp_c}°C)",
            "heat_output_kw": result_b.total_heat_output_kw,
            "supply_temp_c": result_b.supply_temp_c,
            "return_temp_c": result_b.return_temp_c,
            "mass_flow_kg_s": result_b.mass_flow_kg_s,
            "pressure_drop_bar": round(result_b.pressure_supply_bar - result_b.pressure_return_bar, 3),
            "status": result_b.status,
        },
        "comparison_summary": {
            "heat_output_difference_kw": round(heat_diff, 2),
            "higher_heat_output_scenario": better,
            "recommendation": f"Scenario {better} delivers more heat output for the given network configuration."
        }
    }
    return json.dumps(comparison, indent=2)


@tool
def explain_geothermal_concept(concept: str) -> str:
    """
    Provide a brief technical explanation of a geothermal or district
    heating concept. Use this when the user asks 'what is X' or
    'explain Y' about energy system components.

    Args:
        concept: The concept to explain (e.g. 'geothermal doublet',
                 'district heating return temperature', 'pressure drop')
    """
    explanations = {
        "geothermal doublet": (
            "A geothermal doublet consists of two boreholes: one production well "
            "that extracts hot water from deep underground (1-5 km), and one injection "
            "well that returns the cooled water back into the reservoir. "
            "This forms a closed loop that sustainably harvests geothermal heat "
            "without depleting groundwater."
        ),
        "district heating": (
            "District heating is a centralized system where heat is produced at one "
            "or more locations and distributed to multiple buildings via insulated "
            "underground pipes carrying hot water. It's more efficient than individual "
            "boilers and ideal for integrating geothermal or waste heat sources."
        ),
        "supply temperature": (
            "The supply temperature (Vorlauftemperatur) is the temperature of hot water "
            "leaving the heat source toward consumers. Higher supply temperatures mean "
            "more heat delivery potential but also higher heat losses in pipes. "
            "Geothermal systems typically supply 60–100°C."
        ),
        "return temperature": (
            "The return temperature (Rücklauftemperatur) is the temperature of water "
            "flowing back to the heat source after consumers have extracted heat. "
            "Lower return temperatures mean more heat was extracted — improving efficiency. "
            "Typical values: 40–60°C for district heating."
        ),
        "pressure drop": (
            "Pressure drop in a pipe network is caused by friction between the fluid "
            "and pipe walls. Higher flow velocities or longer/narrower pipes cause "
            "greater pressure drops, requiring more pump energy to maintain circulation."
        ),
        "mass flow": (
            "Mass flow (kg/s) describes how much water flows through the network per second. "
            "Together with the temperature difference (ΔT) between supply and return, "
            "it determines the total heat output: Q = ṁ × cp × ΔT."
        ),
    }

    concept_lower = concept.lower().strip()
    for key, explanation in explanations.items():
        if key in concept_lower or concept_lower in key:
            return explanation

    return (
        f"I don't have a pre-stored explanation for '{concept}', but I can run a simulation "
        "to demonstrate its effects numerically. Try asking me to simulate a scenario that "
        "varies this parameter!"
    )


# ─────────────────────────────────────────────
# Build the LangGraph Agent
# ─────────────────────────────────────────────

TOOLS = [
    run_heating_network_simulation,
    compare_scenarios,
    explain_geothermal_concept,
]

SYSTEM_PROMPT = """You are GeoSim Assistant — an AI agent specialized in deep geothermal 
district heating network simulation using pandapipes.

You help researchers, engineers, and municipal planners understand and analyze 
geothermal heating networks through:
- Running thermohydraulic simulations (temperatures, pressures, mass flows, heat output)
- Comparing different network scenarios (high-temp vs low-temp, different configurations)
- Explaining geothermal and district heating concepts clearly

When a user asks about network performance, always run a simulation to provide 
real numerical results rather than estimates.

When presenting results:
1. Lead with the key metric (heat output, temperature levels)  
2. Explain what the numbers mean in practical terms
3. Highlight any potential issues (low pressure, high heat loss, etc.)
4. Suggest follow-up analyses if relevant
"""


def create_agent(model_name: str = "llama-3.1-8b-instant", groq_api_key: str = None):
    """Create and return the LangGraph agent."""

    llm = ChatGroq(
        model=model_name,
        api_key=groq_api_key,
    ).bind_tools(TOOLS)

    tool_map = {t.name: t for t in TOOLS}

    # ── Node: call LLM ──
    def call_llm(state: AgentState) -> dict:
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = llm.invoke(messages)
        return {"messages": [response]}

    # ── Node: execute tools ──
    def call_tools(state: AgentState) -> dict:
        last_message = state["messages"][-1]
        tool_messages = []
        new_results = []

        for tool_call in last_message.tool_calls:
            tool_fn = tool_map.get(tool_call["name"])
            if tool_fn:
                result = tool_fn.invoke(tool_call["args"])
                tool_messages.append(
                    ToolMessage(content=str(result), tool_call_id=tool_call["id"])
                )
                new_results.append({"tool": tool_call["name"], "result": result})

        return {
            "messages": tool_messages,
            "simulation_results": state.get("simulation_results", []) + new_results,
        }

    # ── Routing ──
    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if hasattr(last, "tool_calls") and last.tool_calls:
            return "tools"
        return END

    # ── Build graph ──
    graph = StateGraph(AgentState)
    graph.add_node("llm", call_llm)
    graph.add_node("tools", call_tools)
    graph.set_entry_point("llm")
    graph.add_conditional_edges("llm", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "llm")

    return graph.compile()
