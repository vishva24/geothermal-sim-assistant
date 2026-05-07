"""
District Heating Network Simulation using pandapipes.
Models a simplified deep geothermal district heating network
with a geothermal source, circulation pump, pipes, and consumers.
"""

import pandapipes as pp
import pandas as pd
from dataclasses import dataclass
from typing import Optional


@dataclass
class SimulationResult:
    """Structured result from a network simulation."""
    supply_temp_c: float
    return_temp_c: float
    mass_flow_kg_s: float
    pressure_supply_bar: float
    pressure_return_bar: float
    pipe_velocities: dict
    junction_pressures: dict
    junction_temperatures: dict
    total_heat_output_kw: float
    network_efficiency_pct: float
    status: str = "converged"


def build_district_heating_network(
    supply_temp_k: float = 363.15,       # 90°C supply
    return_temp_k: float = 333.15,        # 60°C return
    geothermal_pressure_bar: float = 6.0,
    consumer_mass_flow: float = 0.5,      # kg/s per consumer
    n_consumers: int = 3,
    pipe_length_km: float = 0.5,
    pipe_diameter_m: float = 0.1,
) -> pp.pandapipesNet:
    """
    Build a district heating network with a geothermal heat source.

    Layout:
        GeoSource (j0) → Pump → Supply Pipe → Junction (j1)
                                                  ├─ Consumer 1 (j2)
                                                  ├─ Consumer 2 (j3)
                                                  └─ Consumer 3 (j4)
                                                  └─ Return pipe → j0
    """
    net = pp.create_empty_network(fluid="water")

    # --- Junctions ---
    j_source = pp.create_junction(net, pn_bar=geothermal_pressure_bar,
                                   tfluid_k=supply_temp_k, name="Geothermal_Source")
    j_supply = pp.create_junction(net, pn_bar=geothermal_pressure_bar,
                                   tfluid_k=supply_temp_k, name="Supply_Header")
    consumer_junctions = []
    for i in range(n_consumers):
        j = pp.create_junction(net, pn_bar=geothermal_pressure_bar - 1.0,
                                tfluid_k=supply_temp_k, name=f"Consumer_{i+1}")
        consumer_junctions.append(j)

    j_return = pp.create_junction(net, pn_bar=geothermal_pressure_bar - 2.0,
                                   tfluid_k=return_temp_k, name="Return_Header")

    # --- Geothermal source (external grid = fixed pressure/temp boundary) ---
    pp.create_ext_grid(net, junction=j_source,
                       p_bar=geothermal_pressure_bar,
                       t_k=supply_temp_k,
                       name="Geothermal_Doublet")

    # --- Circulation pump ---
    pp.create_circ_pump_const_pressure(
        net,
        return_junction=j_return,
        flow_junction=j_source,
        p_flow_bar=geothermal_pressure_bar,
        plift_bar=2.5,
        t_flow_k=supply_temp_k,
        name="Circulation_Pump"
    )

    # --- Supply pipe: source → supply header ---
    pp.create_pipe_from_parameters(
        net,
        from_junction=j_source,
        to_junction=j_supply,
        length_km=0.2,
        diameter_m=pipe_diameter_m * 1.5,
        name="Main_Supply_Pipe",
        alpha_w_per_m2k=0.5,
        text_k=283.15
    )

    # --- Distribution pipes: supply header → each consumer ---
    for i, j_consumer in enumerate(consumer_junctions):
        pp.create_pipe_from_parameters(
            net,
            from_junction=j_supply,
            to_junction=j_consumer,
            length_km=pipe_length_km,
            diameter_m=pipe_diameter_m,
            name=f"Supply_Pipe_Consumer_{i+1}",
            alpha_w_per_m2k=0.5,
            text_k=283.15
        )

    # --- Heat consumers (sinks with fixed mass flow) ---
    for i, j_consumer in enumerate(consumer_junctions):
        pp.create_sink(
            net,
            junction=j_consumer,
            mdot_kg_per_s=consumer_mass_flow,
            name=f"Heat_Consumer_{i+1}"
        )

    # --- Return pipes: consumers → return header ---
    for i, j_consumer in enumerate(consumer_junctions):
        pp.create_pipe_from_parameters(
            net,
            from_junction=j_consumer,
            to_junction=j_return,
            length_km=pipe_length_km,
            diameter_m=pipe_diameter_m,
            name=f"Return_Pipe_Consumer_{i+1}",
            alpha_w_per_m2k=0.5,
            text_k=283.15
        )

    return net


def run_simulation(net: pp.pandapipesNet) -> SimulationResult:
    """Run pipeflow simulation and extract structured results."""
    try:
        pp.pipeflow(net, mode="all")  # hydraulic + heat transfer

        # Extract junction results
        j_pressures = net.res_junction["p_bar"].to_dict()
        j_temps = {k: v - 273.15 for k, v in net.res_junction["t_k"].to_dict().items()}

        # Supply and return temps (first and last junction)
        supply_temp_c = list(j_temps.values())[0]
        return_temp_c = list(j_temps.values())[-1]

        # Pipe velocities
        pipe_velocities = net.res_pipe["v_mean_m_per_s"].to_dict() if "v_mean_m_per_s" in net.res_pipe.columns else {}

        # Mass flow from ext_grid result
        total_mass_flow = net.res_ext_grid["mdot_kg_per_s"].sum() if len(net.res_ext_grid) > 0 else 0.0

        # Heat output: Q = mdot * cp * delta_T  (cp_water ≈ 4186 J/kg·K)
        cp_water = 4186
        delta_t = supply_temp_c - return_temp_c
        total_heat_kw = abs(total_mass_flow * cp_water * delta_t / 1000)

        # Efficiency: ratio of useful heat to theoretical max
        max_theoretical_heat = abs(total_mass_flow * cp_water * delta_t / 1000)
        efficiency = (total_heat_kw / max_theoretical_heat * 100) if max_theoretical_heat > 0 else 0.0

        supply_pressure = list(j_pressures.values())[0]
        return_pressure = list(j_pressures.values())[-1]

        return SimulationResult(
            supply_temp_c=round(supply_temp_c, 2),
            return_temp_c=round(return_temp_c, 2),
            mass_flow_kg_s=round(abs(total_mass_flow), 4),
            pressure_supply_bar=round(supply_pressure, 3),
            pressure_return_bar=round(return_pressure, 3),
            pipe_velocities={k: round(v, 4) for k, v in pipe_velocities.items()},
            junction_pressures={k: round(v, 3) for k, v in j_pressures.items()},
            junction_temperatures={k: round(v, 2) for k, v in j_temps.items()},
            total_heat_output_kw=round(total_heat_kw, 2),
            network_efficiency_pct=round(min(efficiency, 100.0), 2),
            status="converged"
        )

    except Exception as e:
        return SimulationResult(
            supply_temp_c=0, return_temp_c=0, mass_flow_kg_s=0,
            pressure_supply_bar=0, pressure_return_bar=0,
            pipe_velocities={}, junction_pressures={}, junction_temperatures={},
            total_heat_output_kw=0, network_efficiency_pct=0,
            status=f"failed: {str(e)}"
        )
