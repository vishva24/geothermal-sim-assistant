"""
Benchmark evaluator for the GeoThermal Sim Assistant agent.

Metrics
-------
1. Parameter Extraction Accuracy  – how well the agent extracts params from the prompt
2. Simulation Correctness Score   – how close the tool result is to pandapipes ground truth
3. Latency                        – total, pandapipes-only, and estimated LLM time
"""

import io
import json
import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
elif hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Allow imports from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent.agent import create_agent
from simulation.network import build_district_heating_network, run_simulation

# ── Paths ────────────────────────────────────────────────────────────────────

BENCHMARK_DIR = Path(__file__).parent
TEST_CASES_PATH = BENCHMARK_DIR / "test_cases.json"
REPORT_PATH    = BENCHMARK_DIR / "eval_report.json"
CHART_PATH     = BENCHMARK_DIR / "eval_chart.png"

# ── Tolerances ────────────────────────────────────────────────────────────────

PARAM_TOLERANCE = 0.01       # 1%  – parameter extraction
SIM_TIGHT_TOLERANCE = 0.02   # 2%  – full sim-correctness score
SIM_LOOSE_TOLERANCE = 0.05   # 5%  – half sim-correctness score
PASS_THRESHOLD = 0.80        # both metrics must reach 80% to pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _within(actual: float, expected: float, tol: float) -> bool:
    if expected == 0:
        return actual == 0
    return abs(actual - expected) / abs(expected) <= tol


def _extract_tool_call(messages: list) -> tuple[str | None, dict | None]:
    """Return (tool_name, args) from the first AIMessage that contains a tool call."""
    for msg in messages:
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            tc = msg.tool_calls[0]
            return tc["name"], tc["args"]
    return None, None


def _extract_tool_result(messages: list) -> dict | None:
    """Parse the JSON payload from the first ToolMessage."""
    for msg in messages:
        if isinstance(msg, ToolMessage):
            try:
                return json.loads(msg.content)
            except (json.JSONDecodeError, TypeError):
                return None
    return None


# ── Metric 1: Parameter Extraction ───────────────────────────────────────────

def score_param_extraction(
    extracted_args: dict | None,
    expected_params: dict,
) -> tuple[float, dict]:
    """
    Compare each key in expected_params against extracted_args.
    Numeric values use PARAM_TOLERANCE; string values require exact match.
    Returns (score 0-1, per-param detail dict).
    """
    if extracted_args is None:
        return 0.0, {"error": "agent made no tool call"}

    total = len(expected_params)
    correct = 0
    details: dict = {}

    for param, expected_val in expected_params.items():
        actual_val = extracted_args.get(param)
        if actual_val is None:
            details[param] = {"expected": expected_val, "actual": None, "correct": False}
            continue

        if isinstance(expected_val, (int, float)):
            ok = _within(float(actual_val), float(expected_val), PARAM_TOLERANCE)
        else:
            ok = actual_val == expected_val

        details[param] = {"expected": expected_val, "actual": actual_val, "correct": ok}
        if ok:
            correct += 1

    score = correct / total if total > 0 else 0.0
    return round(score, 4), details


# ── Metric 2: Simulation Correctness ─────────────────────────────────────────

def _heat_score(actual: float | None, expected: float) -> float:
    if actual is None:
        return 0.0
    if _within(actual, expected, SIM_TIGHT_TOLERANCE):
        return 1.0
    if _within(actual, expected, SIM_LOOSE_TOLERANCE):
        return 0.5
    return 0.0


def score_simulation_correctness(
    tool_result: dict | None,
    ground_truth: dict,
    tool_name: str | None,
) -> tuple[float, dict]:
    """
    Compare the tool's JSON result to pre-computed ground truth.

    - run_heating_network_simulation: checks total_heat_output_kw,
      supply_temperature_c, return_temperature_c
    - compare_scenarios: averages heat scores for scenario_A and scenario_B
    """
    if tool_result is None:
        return 0.0, {"error": "no tool result in message history"}

    details: dict = {}

    if tool_name == "run_heating_network_simulation":
        actual_heat = tool_result.get("total_heat_output_kw")
        actual_supply = tool_result.get("supply_temperature_c")
        actual_return = tool_result.get("return_temperature_c")

        hs = _heat_score(actual_heat, ground_truth["total_heat_output_kw"])
        details["total_heat_output_kw"] = {
            "expected": ground_truth["total_heat_output_kw"],
            "actual": actual_heat,
            "score": hs,
        }
        details["supply_temp_c"] = {
            "expected": ground_truth["supply_temp_c"],
            "actual": actual_supply,
            "match": actual_supply is not None and _within(
                actual_supply, ground_truth["supply_temp_c"], SIM_TIGHT_TOLERANCE
            ),
        }
        details["return_temp_c"] = {
            "expected": ground_truth["return_temp_c"],
            "actual": actual_return,
            "match": actual_return is not None and _within(
                actual_return, ground_truth["return_temp_c"], SIM_TIGHT_TOLERANCE
            ),
        }
        return hs, details

    if tool_name == "compare_scenarios":
        res_a = tool_result.get("scenario_A", {})
        res_b = tool_result.get("scenario_B", {})
        gt_a = ground_truth["scenario_a"]
        gt_b = ground_truth["scenario_b"]

        score_a = _heat_score(res_a.get("heat_output_kw"), gt_a["total_heat_output_kw"])
        score_b = _heat_score(res_b.get("heat_output_kw"), gt_b["total_heat_output_kw"])

        details["scenario_A_heat"] = {
            "expected": gt_a["total_heat_output_kw"],
            "actual": res_a.get("heat_output_kw"),
            "score": score_a,
        }
        details["scenario_B_heat"] = {
            "expected": gt_b["total_heat_output_kw"],
            "actual": res_b.get("heat_output_kw"),
            "score": score_b,
        }
        return round((score_a + score_b) / 2, 4), details

    return 0.0, {"error": f"unrecognised tool: {tool_name}"}


# ── Metric 3: Pandapipes baseline time ───────────────────────────────────────

def _time_pandapipes(tool_name: str | None, args: dict) -> float:
    """Run the equivalent simulation directly and return wall-clock seconds."""
    if tool_name is None:
        return 0.0

    t0 = time.perf_counter()

    if tool_name == "run_heating_network_simulation":
        net = build_district_heating_network(
            supply_temp_k=float(args.get("supply_temp_c", 90.0)) + 273.15,
            return_temp_k=float(args.get("return_temp_c", 60.0)) + 273.15,
            geothermal_pressure_bar=float(args.get("geothermal_pressure_bar", 6.0)),
            consumer_mass_flow=float(args.get("consumer_mass_flow_kg_s", 0.5)),
            n_consumers=int(args.get("n_consumers", 3)),
            pipe_length_km=float(args.get("pipe_length_km", 0.5)),
            pipe_diameter_m=float(args.get("pipe_diameter_m", 0.1)),
        )
        run_simulation(net)

    elif tool_name == "compare_scenarios":
        for supply_c, return_c in [
            (args.get("scenario_a_supply_temp_c", 90.0), args.get("scenario_a_return_temp_c", 60.0)),
            (args.get("scenario_b_supply_temp_c", 70.0), args.get("scenario_b_return_temp_c", 40.0)),
        ]:
            net = build_district_heating_network(
                supply_temp_k=float(supply_c) + 273.15,
                return_temp_k=float(return_c) + 273.15,
                consumer_mass_flow=float(args.get("consumer_mass_flow_kg_s", 0.5)),
                n_consumers=int(args.get("n_consumers", 3)),
            )
            run_simulation(net)

    return time.perf_counter() - t0


# ── Main evaluation loop ──────────────────────────────────────────────────────

def evaluate() -> None:
    groq_api_key = os.getenv("groq_api_key")
    if not groq_api_key:
        print("ERROR: groq_api_key not found. Set it in .env or the environment.")
        sys.exit(1)

    with open(TEST_CASES_PATH) as f:
        test_cases: list[dict] = json.load(f)

    agent = create_agent(groq_api_key=groq_api_key)

    per_test: list[dict] = []

    for tc in test_cases:
        tc_id = tc["id"]
        prompt = tc["user_prompt"]
        expected_tool = tc["expected_tool"]
        expected_params = tc["expected_params"]
        ground_truth = tc["ground_truth"]

        print(f"\n── {tc_id}  {prompt[:65]}{'…' if len(prompt) > 65 else ''}")

        # ── Invoke agent ──────────────────────────────────────────────────────
        t_start = time.perf_counter()
        state = agent.invoke({
            "messages": [HumanMessage(content=prompt)],
            "simulation_results": [],
            "current_params": {},
        })
        total_s = time.perf_counter() - t_start

        messages = state["messages"]

        # ── Parse tool interaction ─────────────────────────────────────────────
        tool_name, extracted_args = _extract_tool_call(messages)
        tool_result = _extract_tool_result(messages)
        tool_correct = tool_name == expected_tool

        # ── Metric 1 ──────────────────────────────────────────────────────────
        param_score, param_details = score_param_extraction(extracted_args, expected_params)

        # ── Metric 2 ──────────────────────────────────────────────────────────
        # Use the tool that was actually called for key mapping; fall back to
        # expected_tool so the error message is still informative.
        sim_score, sim_details = score_simulation_correctness(
            tool_result, ground_truth, tool_name or expected_tool
        )

        # ── Metric 3 ──────────────────────────────────────────────────────────
        sim_s = _time_pandapipes(tool_name, extracted_args or {})
        llm_s = max(0.0, total_s - sim_s)

        # ── Pass / fail ───────────────────────────────────────────────────────
        passed = param_score >= PASS_THRESHOLD and sim_score >= PASS_THRESHOLD

        result = {
            "id": tc_id,
            "user_prompt": prompt,
            "expected_tool": expected_tool,
            "tool_selected": tool_name,
            "tool_correct": tool_correct,
            "param_extraction_score": param_score,
            "param_details": param_details,
            "simulation_correctness_score": sim_score,
            "simulation_details": sim_details,
            "latency": {
                "total_s": round(total_s, 3),
                "pandapipes_s": round(sim_s, 3),
                "llm_estimated_s": round(llm_s, 3),
            },
            "passed": passed,
        }
        per_test.append(result)

        status_label = "PASS" if passed else "FAIL"
        tool_mark = "✓" if tool_correct else "✗"
        print(f"   Tool: {tool_name} ({tool_mark})  |  {status_label}")
        print(
            f"   Param: {param_score:.0%}  |  Sim: {sim_score:.0%}  |  "
            f"Latency: {total_s:.2f}s  ({sim_s:.3f}s sim + {llm_s:.2f}s LLM)"
        )

    # ── Aggregate ─────────────────────────────────────────────────────────────
    n = len(per_test)
    aggregate = {
        "total_tests": n,
        "passed": sum(1 for r in per_test if r["passed"]),
        "failed": sum(1 for r in per_test if not r["passed"]),
        "avg_param_extraction_score": round(
            sum(r["param_extraction_score"] for r in per_test) / n, 4
        ),
        "avg_simulation_correctness_score": round(
            sum(r["simulation_correctness_score"] for r in per_test) / n, 4
        ),
        "avg_latency_total_s": round(
            sum(r["latency"]["total_s"] for r in per_test) / n, 3
        ),
        "avg_latency_pandapipes_s": round(
            sum(r["latency"]["pandapipes_s"] for r in per_test) / n, 3
        ),
        "avg_latency_llm_estimated_s": round(
            sum(r["latency"]["llm_estimated_s"] for r in per_test) / n, 3
        ),
    }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": "llama-3.1-8b-instant",
        "thresholds": {
            "param_tolerance_pct": PARAM_TOLERANCE * 100,
            "sim_tight_tolerance_pct": SIM_TIGHT_TOLERANCE * 100,
            "sim_loose_tolerance_pct": SIM_LOOSE_TOLERANCE * 100,
            "pass_threshold_pct": PASS_THRESHOLD * 100,
        },
        "aggregate": aggregate,
        "test_results": per_test,
    }

    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"  {aggregate['passed']}/{n} tests passed")
    print(f"  Avg param extraction : {aggregate['avg_param_extraction_score']:.1%}")
    print(f"  Avg sim correctness  : {aggregate['avg_simulation_correctness_score']:.1%}")
    print(f"  Avg total latency    : {aggregate['avg_latency_total_s']:.2f}s")
    print(f"  Avg pandapipes time  : {aggregate['avg_latency_pandapipes_s']:.3f}s")
    print(f"  Avg LLM est. time    : {aggregate['avg_latency_llm_estimated_s']:.2f}s")
    print(f"\n  Report -> {REPORT_PATH}")
    print("=" * 60)

    # ── Optional integrations ─────────────────────────────────────────────────
    print()
    _log_to_mlflow(report, per_test)
    _upload_to_s3()


# ── MLflow logging ────────────────────────────────────────────────────────────

def _log_to_mlflow(report: dict, per_test: list[dict]) -> None:
    """Log aggregate metrics, per-test step metrics, and the JSON report artifact."""
    try:
        import mlflow  # noqa: PLC0415
    except ImportError:
        print("  [mlflow] not installed — skipping experiment tracking.")
        return

    agg = report["aggregate"]
    mlflow.set_experiment("geosim-agent-eval")

    with mlflow.start_run():
        # Thresholds / config as params
        for k, v in report["thresholds"].items():
            mlflow.log_param(k, v)
        mlflow.log_param("model", report["model"])
        mlflow.log_param("total_tests", agg["total_tests"])

        # Aggregate metrics
        mlflow.log_metric("pass_rate", agg["passed"] / agg["total_tests"])
        mlflow.log_metric("avg_param_extraction_score", agg["avg_param_extraction_score"])
        mlflow.log_metric("avg_simulation_correctness_score", agg["avg_simulation_correctness_score"])
        mlflow.log_metric("avg_latency_total_s", agg["avg_latency_total_s"])
        mlflow.log_metric("avg_latency_pandapipes_s", agg["avg_latency_pandapipes_s"])
        mlflow.log_metric("avg_latency_llm_estimated_s", agg["avg_latency_llm_estimated_s"])

        # Per-test metrics logged as steps (step = test index)
        for i, r in enumerate(per_test):
            mlflow.log_metric("param_extraction_score", r["param_extraction_score"], step=i)
            mlflow.log_metric("simulation_correctness_score", r["simulation_correctness_score"], step=i)
            mlflow.log_metric("latency_total_s", r["latency"]["total_s"], step=i)

        # Artifacts
        mlflow.log_artifact(str(REPORT_PATH))
        if CHART_PATH.exists():
            mlflow.log_artifact(str(CHART_PATH))

        run_id = mlflow.active_run().info.run_id
        print(f"  [mlflow] run logged → run_id: {run_id}")


# ── AWS S3 upload ─────────────────────────────────────────────────────────────

def _upload_to_s3() -> None:
    """Upload the JSON report and chart PNG to S3 if configured."""
    bucket = os.getenv("S3_BUCKET_NAME")
    if not bucket:
        print("  [s3] S3_BUCKET_NAME not set — skipping upload.")
        return

    try:
        import boto3  # noqa: PLC0415
        from botocore.exceptions import BotoCoreError, ClientError  # noqa: PLC0415
    except ImportError:
        print("  [s3] boto3 not installed — skipping upload.")
        return

    s3 = boto3.client("s3")
    files_to_upload = [
        (REPORT_PATH, "geosim-eval/eval_report.json"),
        (CHART_PATH, "geosim-eval/eval_chart.png"),
    ]

    for local_path, s3_key in files_to_upload:
        if not local_path.exists():
            continue
        try:
            s3.upload_file(str(local_path), bucket, s3_key)
            print(f"  [s3] uploaded s3://{bucket}/{s3_key}")
        except (BotoCoreError, ClientError) as exc:
            print(f"  [s3] upload failed for {local_path.name}: {exc}")


if __name__ == "__main__":
    evaluate()
