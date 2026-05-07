"""
benchmark/report.py

Read benchmark/eval_report.json and produce:
  1. A formatted terminal summary + per-test breakdown table
  2. benchmark/eval_chart.png  — bar (param accuracy) + line (sim correctness)

Usage:  python -m benchmark.report
"""

import io
import json
import sys
from pathlib import Path

# Ensure box-drawing characters render correctly on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
elif hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Paths ─────────────────────────────────────────────────────────────────────

BENCHMARK_DIR = Path(__file__).parent
REPORT_PATH   = BENCHMARK_DIR / "eval_report.json"
CHART_PATH    = BENCHMARK_DIR / "eval_chart.png"


# ── Table-drawing helpers ─────────────────────────────────────────────────────

# Column spec: (header, width, alignment)  alignment: '<' left  '>' right  '^' center
_COLS = [
    ("ID",          8,  "<"),
    ("Prompt",     46,  "<"),
    ("Param %",     8,  ">"),
    ("Sim %",       7,  ">"),
    ("Latency",     9,  ">"),
    ("Status",      7,  "^"),
]

_INNER_WIDTH = sum(w for _, w, _ in _COLS) + len(_COLS) - 1   # widths + inner separators


def _cell(text: str, width: int, align: str) -> str:
    text = str(text)
    if len(text) > width:
        text = text[: width - 1] + "…"
    return f"{text:{align}{width}}"


def _row(*values) -> str:
    cells = [_cell(v, w, a) for v, (_, w, a) in zip(values, _COLS)]
    return "│ " + " │ ".join(cells) + " │"


def _hline(left: str, mid: str, right: str, fill: str = "─") -> str:
    segs = [fill * (w + 2) for _, w, _ in _COLS]
    return left + mid.join(segs) + right


def _box_line(text: str, width: int) -> str:
    return f"│  {text:<{width - 2}}│"


# ── Terminal output ───────────────────────────────────────────────────────────

def print_report(data: dict) -> None:
    agg      = data["aggregate"]
    results  = data["test_results"]
    model    = data.get("model", "—")
    gen_at   = data.get("generated_at", "—")

    n         = agg["total_tests"]
    passed    = agg["passed"]
    param_avg = agg["avg_param_extraction_score"]
    sim_avg   = agg["avg_simulation_correctness_score"]
    lat_total = agg["avg_latency_total_s"]
    lat_sim   = agg["avg_latency_pandapipes_s"]

    # ── Summary box ──────────────────────────────────────────────────────────
    BOX_W = 55                        # inner width (between the │ chars)
    title = "GeoSim Agent Evaluation Report"

    print()
    print("┌" + "─" * BOX_W + "┐")
    print("│" + title.center(BOX_W) + "│")
    print("├" + "─" * BOX_W + "┤")

    def _sline(label: str, value: str) -> None:
        row = f"  {label:<28}{value}"
        print("│" + f"{row:<{BOX_W}}" + "│")

    _sline("Model:",                  model)
    _sline("Generated:",              gen_at[:19].replace("T", "  "))
    print("│" + " " * BOX_W + "│")
    _sline("Test Cases:",             str(n))
    _sline("Parameter Extraction:",   f"{param_avg:.1%}")
    _sline("Simulation Correctness:", f"{sim_avg:.1%}")
    _sline("Avg Total Latency:",      f"{lat_total:.2f}s")
    _sline("Avg Simulation Latency:", f"{lat_sim:.3f}s")
    _sline("Pass Rate:",              f"{passed}/{n}")
    print("└" + "─" * BOX_W + "┘")

    # ── Per-test breakdown table ──────────────────────────────────────────────
    print()
    print(_hline("┌", "┬", "┐"))
    print(_row("ID", "Prompt", "Param %", "Sim %", "Latency", "Status"))
    print(_hline("├", "┼", "┤"))

    for i, r in enumerate(results):
        prompt_short = r["user_prompt"]
        param_pct    = f"{r['param_extraction_score']:.0%}"
        sim_pct      = f"{r['simulation_correctness_score']:.0%}"
        latency      = f"{r['latency']['total_s']:.2f}s"
        status       = "PASS" if r["passed"] else "FAIL"

        print(_row(r["id"], prompt_short, param_pct, sim_pct, latency, status))

        if i < len(results) - 1:
            print(_hline("├", "┼", "┤"))

    print(_hline("└", "┴", "┘"))

    # ── Failed cases (if any) ─────────────────────────────────────────────────
    failed = [r for r in results if not r["passed"]]
    if failed:
        print(f"\n  Failed tests ({len(failed)}):")
        for r in failed:
            p = r["param_extraction_score"]
            s = r["simulation_correctness_score"]
            print(f"    {r['id']}  param={p:.0%}  sim={s:.0%}  — {r['user_prompt'][:60]}")
    print()


# ── Matplotlib chart ──────────────────────────────────────────────────────────

def save_chart(data: dict) -> None:
    import matplotlib.pyplot as plt
    import matplotlib.ticker as mticker

    results  = data["test_results"]
    agg      = data["aggregate"]
    model    = data.get("model", "")

    ids        = [r["id"] for r in results]
    x          = list(range(len(ids)))
    param_pcts = [r["param_extraction_score"] * 100 for r in results]
    sim_pcts   = [r["simulation_correctness_score"] * 100 for r in results]

    fig, ax = plt.subplots(figsize=(13, 5.5))
    fig.patch.set_facecolor("#fafafa")
    ax.set_facecolor("#fafafa")

    # ── Bars: parameter extraction ────────────────────────────────────────────
    bar_color  = "#4C72B0"
    pass_color = "#55A868"
    fail_color = "#C44E52"

    bar_colors = [pass_color if v >= 80 else fail_color for v in param_pcts]
    bars = ax.bar(
        x,
        param_pcts,
        width=0.55,
        color=bar_colors,
        alpha=0.82,
        zorder=2,
        label="Parameter Extraction %",
    )

    # Value labels on bars
    for bar, val in zip(bars, param_pcts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1.2,
            f"{val:.0f}%",
            ha="center",
            va="bottom",
            fontsize=8,
            color="#333333",
        )

    # ── Line: simulation correctness ──────────────────────────────────────────
    line_color = "#DD8452"
    ax.plot(
        x,
        sim_pcts,
        color=line_color,
        linewidth=2.0,
        marker="D",
        markersize=6,
        markerfacecolor="white",
        markeredgewidth=1.8,
        markeredgecolor=line_color,
        zorder=3,
        label="Simulation Correctness %",
    )

    # ── Pass threshold line ───────────────────────────────────────────────────
    ax.axhline(
        80,
        color="#888888",
        linewidth=1.0,
        linestyle="--",
        zorder=1,
        label="Pass threshold (80%)",
    )

    # ── Axes cosmetics ────────────────────────────────────────────────────────
    ax.set_xticks(x)
    ax.set_xticklabels(ids, rotation=30, ha="right", fontsize=9)
    ax.set_ylim(0, 115)
    ax.yaxis.set_major_formatter(mticker.PercentFormatter())
    ax.set_ylabel("Score", fontsize=10, labelpad=8)
    ax.set_xlabel("Test Case", fontsize=10, labelpad=8)

    # Remove top + right spines for academic look
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cccccc")
    ax.spines["bottom"].set_color("#cccccc")
    ax.tick_params(colors="#555555")
    ax.yaxis.label.set_color("#555555")
    ax.xaxis.label.set_color("#555555")

    # Subtle horizontal guides only
    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.yaxis.grid(True, color="#e0e0e0", linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)

    # ── Title & subtitle ──────────────────────────────────────────────────────
    title = "GeoSim Agent Evaluation — Parameter Extraction & Simulation Correctness"
    ax.set_title(title, fontsize=12, fontweight="bold", pad=14, color="#222222")

    passed   = agg["passed"]
    n        = agg["total_tests"]
    p_avg    = agg["avg_param_extraction_score"] * 100
    s_avg    = agg["avg_simulation_correctness_score"] * 100
    lat_avg  = agg["avg_latency_total_s"]
    subtitle = (
        f"Model: {model}   |   Pass rate: {passed}/{n}   |   "
        f"Avg param: {p_avg:.1f}%   |   Avg sim: {s_avg:.1f}%   |   "
        f"Avg latency: {lat_avg:.2f}s"
    )
    fig.text(
        0.5, 0.97, subtitle,
        ha="center", va="top",
        fontsize=8, color="#666666",
        transform=fig.transFigure,
    )

    # ── Legend ────────────────────────────────────────────────────────────────
    leg = ax.legend(
        loc="lower right",
        fontsize=9,
        framealpha=0.9,
        edgecolor="#cccccc",
    )
    leg.get_frame().set_linewidth(0.8)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(CHART_PATH, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  Chart saved → {CHART_PATH}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not REPORT_PATH.exists():
        print(f"ERROR: {REPORT_PATH} not found.")
        print("Run the evaluator first:  python -m benchmark.evaluator")
        sys.exit(1)

    with open(REPORT_PATH) as f:
        data = json.load(f)

    print_report(data)
    save_chart(data)


if __name__ == "__main__":
    main()
