"""
Generate docs/images/architecture.png — run once, then delete or keep as source.
Usage: python docs/images/gen_architecture.py
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

OUT = Path(__file__).parent / "architecture.png"

# ── Palette ───────────────────────────────────────────────────────────────────
C_USER       = "#AED6F1"   # light blue
C_CHAINLIT   = "#E67E22"   # orange
C_AGENT      = "#1A5276"   # dark blue
C_TOOLS_BG   = "#1E8449"   # dark green (outer box)
C_TOOLS_SUB  = "#27AE60"   # medium green (sub-boxes)
C_PIPES      = "#C0392B"   # red/coral
C_RESULTS    = "#A9DFBF"   # light green
C_BENCH      = "#7D3C98"   # purple
C_EVALUATOR  = "#4A235A"   # dark purple
C_REPORT     = "#D2B4DE"   # light purple
C_DIVIDER    = "#CCCCCC"
C_ARROW      = "#444444"
C_RETURN     = "#888888"
C_EVAL_ARROW = "#7D3C98"

# ── Figure ────────────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(14, 8))
ax.set_xlim(0, 14)
ax.set_ylim(0, 8)
ax.axis("off")
fig.patch.set_facecolor("white")
ax.set_facecolor("white")

# ── Primitive helpers ─────────────────────────────────────────────────────────

def box(cx, cy, w, h, color, edge="white", lw=2.0, alpha=1.0, zorder=3):
    patch = FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle="round,pad=0.10",
        facecolor=color, edgecolor=edge,
        linewidth=lw, alpha=alpha, zorder=zorder,
    )
    ax.add_patch(patch)

def text(cx, cy, s, size=11, color="#222222", weight="bold",
         style="normal", family="sans-serif", zorder=6):
    ax.text(cx, cy, s, ha="center", va="center",
            fontsize=size, fontweight=weight, fontstyle=style,
            fontfamily=family, color=color, zorder=zorder)

def arrow_h(x1, x2, y, color=C_ARROW, lw=2.0, zorder=2):
    ax.annotate(
        "", xy=(x2, y), xytext=(x1, y),
        arrowprops=dict(arrowstyle="-|>", color=color,
                        lw=lw, mutation_scale=18),
        zorder=zorder,
    )

def arrow_v(x, y1, y2, color=C_ARROW, lw=1.5, zorder=2):
    ax.annotate(
        "", xy=(x, y2), xytext=(x, y1),
        arrowprops=dict(arrowstyle="-|>", color=color,
                        lw=lw, mutation_scale=15),
        zorder=zorder,
    )

# ══════════════════════════════════════════════════════════════════════════════
# TITLE
# ══════════════════════════════════════════════════════════════════════════════
ax.text(7, 7.65, "GeoThermal Sim Assistant — Architecture",
        ha="center", va="center", fontsize=16,
        fontweight="bold", color="#111111")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION LABELS
# ══════════════════════════════════════════════════════════════════════════════
text(0.55, 7.12, "① Agent Pipeline", size=9.5, color="#666666",
     style="italic", weight="normal")
text(0.72, 2.82, "② Evaluation Framework", size=9.5, color="#666666",
     style="italic", weight="normal")

# Dashed separator between sections
ax.plot([0.25, 13.75], [3.15, 3.15],
        color=C_DIVIDER, lw=1.2, ls="--", zorder=1)

# ══════════════════════════════════════════════════════════════════════════════
# MAIN FLOW (top)
# ══════════════════════════════════════════════════════════════════════════════
Y = 5.75          # vertical centre of main boxes
H = 1.40          # height of standard boxes
H_TOOLS = 2.00    # height of tools box (taller to hold sub-labels)

# ── Box geometry: (cx, cy, w) ─────────────────────────────────────────────────
_U  = (1.00,  Y, 1.35)   # User
_CH = (3.00,  Y, 1.65)   # Chainlit UI
_AG = (5.20,  Y, 1.90)   # LangGraph Agent
_TL = (8.15,  Y, 2.90)   # Tools
_PP = (11.00, Y, 1.80)   # pandapipes
_RS = (13.05, Y, 1.45)   # Results

# ── Draw boxes ───────────────────────────────────────────────────────────────
box(*_U,  H,        C_USER,      edge="#85C1E9", lw=1.8)
box(*_CH, H,        C_CHAINLIT,  edge="#D35400", lw=1.8)
box(*_AG, H,        C_AGENT,     edge="#154360", lw=2.0)
box(*_TL, H_TOOLS,  C_TOOLS_BG,  edge="#145A32", lw=2.5)
box(*_PP, H,        C_PIPES,     edge="#922B21", lw=2.0)
box(*_RS, H,        C_RESULTS,   edge="#52BE80", lw=1.8)

# ── Box labels ────────────────────────────────────────────────────────────────
# _X[0]=cx, _X[1]=cy, _X[2]=w
text(_U[0],  Y + 0.22, "User",          size=11, color="#1a1a1a")
text(_U[0],  Y - 0.25, "voice / text",  size=8,  color="#555555", weight="normal", style="italic")

text(_CH[0], Y + 0.22, "Chainlit UI",   size=11, color="#1a1a1a")
text(_CH[0], Y - 0.25, "web · chat",    size=8,  color="#555555", weight="normal", style="italic")

text(_AG[0], Y + 0.22, "LangGraph\nAgent", size=11, color="white")
text(_AG[0], Y - 0.35, "llama-3.1-8b", size=8,  color="#AED6F1", weight="normal", style="italic")

text(_TL[0], Y + 0.73, "Tools",          size=12, color="white")

# Sub-tool boxes inside Tools
_sub_tools = [
    (Y + 0.30, "run_heating_network_simulation"),
    (Y - 0.20, "compare_scenarios"),
    (Y - 0.70, "explain_geothermal_concept"),
]
for sy, name in _sub_tools:
    box(_TL[0], sy, _TL[2] - 0.45, 0.37, C_TOOLS_SUB,
        edge="#145A32", lw=1.0, alpha=0.85, zorder=4)
    ax.text(_TL[0], sy, name, ha="center", va="center",
            fontsize=7.8, fontweight="bold", color="white",
            fontfamily="monospace", zorder=7)

text(_PP[0], Y + 0.22, "pandapipes",    size=11, color="white")
text(_PP[0], Y - 0.28, "thermohydraulic\nsimulation", size=7.5,
     color="#FADBD8", weight="normal", style="italic")

text(_RS[0], Y + 0.22, "Results",       size=11, color="#1a1a1a")
text(_RS[0], Y - 0.25, "JSON · text",   size=8,  color="#555555", weight="normal", style="italic")

# ── Forward arrows ────────────────────────────────────────────────────────────
arrow_h(_U[0]  + _U[2]  / 2, _CH[0] - _CH[2] / 2, Y)
arrow_h(_CH[0] + _CH[2] / 2, _AG[0] - _AG[2] / 2, Y)
arrow_h(_AG[0] + _AG[2] / 2, _TL[0] - _TL[2] / 2, Y)
arrow_h(_TL[0] + _TL[2] / 2, _PP[0] - _PP[2] / 2, Y)
arrow_h(_PP[0] + _PP[2] / 2, _RS[0] - _RS[2] / 2, Y)

# ── Return path (Results → User, routed below boxes) ─────────────────────────
y_ret = Y - H / 2 - 0.60     # horizontal rail below the boxes
x_ret_start = _RS[0] - 0.05
x_ret_end   = _U[0]

# Down from Results box
ax.plot([x_ret_start, x_ret_start],
        [Y - H / 2, y_ret],
        color=C_RETURN, lw=1.6, zorder=2)
# Horizontal rail
ax.plot([x_ret_start, x_ret_end],
        [y_ret, y_ret],
        color=C_RETURN, lw=1.6, zorder=2)
# Up into User box (arrowhead)
arrow_v(x_ret_end, y_ret, Y - H / 2, color=C_RETURN, lw=1.6)
# Label
ax.text(7.1, y_ret - 0.22,
        "natural language response",
        ha="center", va="center",
        fontsize=8.5, color=C_RETURN, style="italic")

# ══════════════════════════════════════════════════════════════════════════════
# EVALUATION FRAMEWORK (bottom)
# ══════════════════════════════════════════════════════════════════════════════
Y_E = 1.80      # vertical centre
H_E = 1.05      # box height

# (cx, cy, w)
_BN = (3.00,  Y_E, 2.10)   # Benchmark
_EV = (7.00,  Y_E, 2.60)   # Evaluator
_RP = (11.10, Y_E, 2.90)   # Report

box(*_BN, H_E, C_BENCH,     edge="#5B2C6F", lw=2.0)
box(*_EV, H_E, C_EVALUATOR, edge="#2C1654", lw=2.0)
box(*_RP, H_E, C_REPORT,    edge="#A569BD", lw=2.0)

text(_BN[0], Y_E + 0.20, "Benchmark",     size=11, color="white")
text(_BN[0], Y_E - 0.24, "10 test cases", size=8.5, color="#D2B4DE",
     weight="normal", style="italic")

text(_EV[0], Y_E + 0.20, "Evaluator",                size=11, color="white")
text(_EV[0], Y_E - 0.24, "param + sim + latency",    size=8.5, color="#D2B4DE",
     weight="normal", style="italic")

text(_RP[0], Y_E + 0.20, "Report",                           size=11, color="#4A235A")
text(_RP[0], Y_E - 0.16, "100% param accuracy",              size=8.2, color="#6C3483",
     weight="normal")
text(_RP[0], Y_E - 0.46, "100% sim correctness · 0.16s sim", size=8.0,
     color="#6C3483", weight="normal")

arrow_h(_BN[0] + _BN[2] / 2, _EV[0] - _EV[2] / 2, Y_E, color=C_EVAL_ARROW)
arrow_h(_EV[0] + _EV[2] / 2, _RP[0] - _RP[2] / 2, Y_E, color=C_EVAL_ARROW)

# ── Dotted connector: main pipeline ↓ Evaluator ──────────────────────────────
y_pipe_bot = Y - H / 2
y_eval_top = Y_E + H_E / 2
x_conn = _EV[0]

ax.plot([x_conn, x_conn], [y_pipe_bot, y_eval_top],
        color=C_EVAL_ARROW, lw=1.2, ls=":", zorder=1)
ax.text(x_conn + 0.22, (y_pipe_bot + y_eval_top) / 2,
        "eval\ndata", ha="left", va="center",
        fontsize=7.5, color=C_EVAL_ARROW, style="italic")

# ── test_cases.json label on Benchmark ───────────────────────────────────────
ax.text(_BN[0], Y_E - H_E / 2 - 0.22,
        "test_cases.json",
        ha="center", va="center",
        fontsize=7.5, color="#7D3C98",
        style="italic", fontfamily="monospace")

# ── eval_report.json label on Report ─────────────────────────────────────────
ax.text(_RP[0], Y_E - H_E / 2 - 0.22,
        "eval_report.json  ·  eval_chart.png",
        ha="center", va="center",
        fontsize=7.5, color="#7D3C98",
        style="italic", fontfamily="monospace")

# ══════════════════════════════════════════════════════════════════════════════
# SAVE
# ══════════════════════════════════════════════════════════════════════════════
fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"Saved -> {OUT}")
