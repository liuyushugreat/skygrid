#!/usr/bin/env python3
"""Regenerate the camera-ready paper figures (scaling, graceful degradation).

Figures are rendered with matplotlib using TrueType (Type 42) fonts so the
resulting PDFs pass IEEE PDF eXpress font checks without a separate
outlining pass.

  python scripts/plot_paper_figs.py --out-dir ../figs

Data sources
------------
* Fig. 3 (scaling): `outputs/scaling/scaling_paper.json`, produced by
  `scripts/run_scaling.py --scaling configs/scaling_paper.yaml` (weak sweep at
  the M density, strong sweep at 10K entities, 60 s, seed 20260928).  Pass
  `--scaling-json` to plot another run.
* Fig. (fault): `outputs/fault/fault.json` from `scripts/run_fault.py`, which
  matches Table VI of the paper exactly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["pdf.fonttype"] = 42  # TrueType, IEEE-compliant
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.rcParams["font.family"] = "DejaVu Sans"
matplotlib.rcParams["font.size"] = 8
matplotlib.rcParams["axes.labelsize"] = 8
matplotlib.rcParams["axes.titlesize"] = 8.5
matplotlib.rcParams["legend.fontsize"] = 7.5
matplotlib.rcParams["xtick.labelsize"] = 7.5
matplotlib.rcParams["ytick.labelsize"] = 7.5
matplotlib.rcParams["axes.linewidth"] = 0.8
matplotlib.rcParams["lines.linewidth"] = 1.4

import matplotlib.pyplot as plt  # noqa: E402

# Okabe-Ito colour-blind-safe palette
C_BLUE = "#0072B2"
C_ORANGE = "#E69F00"
C_GREEN = "#009E73"
C_VERMIL = "#D55E00"
C_GREY = "#555555"

# --- Fig. 3 (scaling) --------------------------------------------------------
SLO_MS = 100.0
DEFAULT_SCALING_JSON = Path(__file__).resolve().parents[1] / "outputs" / "scaling" / "scaling_paper.json"


def _load_scaling(scaling_json: Path) -> tuple[list[dict], list[dict]]:
    """Return (weak, strong) point lists from a run_scaling.py JSON."""
    data = json.loads(scaling_json.read_text())

    def rows(key: str) -> list[dict]:
        out = []
        for r in data[key]:
            m = r["metrics"]
            out.append({
                "edges": int(r["num_edges"]),
                "entities": int(r["num_entities"]),
                "p50": float(m["latency_ms"]["p50"]),
                "p99": float(m["latency_ms"]["p99"]),
                "offered_ops_s": m["num_events"] / float(r["duration_s"]),
                "throughput_ops_s": float(m["throughput_ops"]),
                "edge_cut": float(m["partition_info"].get("edge_cut", 0.0)),
            })
        return sorted(out, key=lambda d: d["edges"])

    return rows("weak"), rows("strong")


def plot_scaling(out: Path, scaling_json: Path | None) -> None:
    """Fig. 3: (a) weak scaling at the M density, (b) strong scaling at 10K.

    Both panels plot p99 against the number of edge units.  In the weak
    sweep the per-edge load is constant (2.5K entities per edge), so
    throughput is simply the offered load; the informative quantity is
    whether the tail stays flat as the fabric grows.  In the strong sweep
    the single-edge point saturates (p99 in seconds) and is drawn clipped
    at the top of the axis with its value annotated.
    """
    weak, strong = _load_scaling(scaling_json or DEFAULT_SCALING_JSON)
    edges = [r["edges"] for r in weak]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(3.45, 1.5))
    fs = 6.3  # tick / annotation font size for the compact layout

    def _panel(ax, pts, title, xlabel, ylim, yticks):
        xs = [r["edges"] for r in pts]
        p99 = [r["p99"] for r in pts]
        p50 = [r["p50"] for r in pts]
        ax.axhline(SLO_MS, ls="--", color=C_VERMIL, lw=1.0, label=f"{SLO_MS:g} ms SLO")
        ax.plot(xs, [min(v, ylim[1]) for v in p99], "-s", color=C_GREEN, ms=3.5,
                label="p99", clip_on=False)
        ax.plot(xs, p50, "-o", color=C_BLUE, ms=3.0, label="p50")
        for x, y in zip(xs, p99):
            if y > ylim[1]:
                ax.annotate(f"{y/1000:.1f} s", (x, ylim[1]), textcoords="offset points",
                            xytext=(6, -8), ha="left", fontsize=5.8, color=C_GREEN)
            else:
                ax.annotate(f"{y:.0f}", (x, y), textcoords="offset points",
                            xytext=(0, 4), ha="center", fontsize=5.8, color=C_GREEN)
        ax.set_xscale("log", base=2)
        ax.set_xticks(xs)
        ax.set_xticklabels([str(e) for e in xs], fontsize=fs)
        ax.tick_params(axis="y", labelsize=fs)
        ax.set_ylim(*ylim)
        ax.set_yticks(yticks)
        ax.set_xlabel(xlabel, fontsize=6.8)
        ax.set_title(title, loc="left", fontsize=7)
        ax.grid(True, which="major", ls=":", lw=0.5, alpha=0.7)

    _panel(ax1, weak, "(a) Weak scaling", "Edge units (2.5K entities each)",
           (0, 150), [0, 50, 100, 150])
    ax1.set_ylabel("Latency (ms)", fontsize=6.8)
    ax1.legend(loc="upper left", frameon=False, fontsize=6, handlelength=1.6,
               borderaxespad=0.2, ncol=3, columnspacing=0.8, handletextpad=0.4)

    _panel(ax2, strong, "(b) Strong scaling", "Edge units (10K entities total)",
           (0, 150), [0, 50, 100, 150])

    fig.tight_layout(w_pad=1.0)
    fig.savefig(out, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"[plot] wrote {out}")


def plot_fault(out: Path, fault_json: Path) -> None:
    data = json.loads(fault_json.read_text())
    profiles = ["healthy", "one-edge-degraded", "two-edges-degraded",
                "one-edge-failed"]
    labels = ["healthy", "1 deg.", "2 deg.", "1 failed"]
    series = {"ldg+cop": ("LDG + COP-H", C_ORANGE), "skygrid": ("SkyGrid", C_BLUE)}

    by_key = {(r["profile"], r["spec"]["label"]): r["metrics"]
              for r in data["rows"]}
    p99 = {k: [] for k in series}
    xedge = {k: [] for k in series}
    for prof in profiles:
        for k in series:
            m = by_key[(prof, k)]
            p99[k].append(m["latency_ms"]["p99"])
            xedge[k].append(m["cross_edge_bytes"] / 1e6)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(3.45, 2.1),
                                   gridspec_kw={"width_ratios": [1.15, 1]})
    import numpy as np
    x = np.arange(len(profiles))
    w = 0.38
    for i, (k, (lab, col)) in enumerate(series.items()):
        ax1.bar(x + (i - 0.5) * w, p99[k], w, color=col, label=lab)
        ax2.bar(x + (i - 0.5) * w, xedge[k], w, color=col, label=lab)
    ax1.axhline(SLO_MS, ls="--", color=C_VERMIL, lw=1.0)
    ax1.text(len(profiles) - 0.55, SLO_MS * 1.25, "100 ms SLO",
             ha="right", fontsize=6.5, color=C_VERMIL)
    ax1.set_yscale("log")
    ax1.set_ylabel("p99 latency (ms, log)")
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=6.3)
    ax1.set_title("(a) p99 latency", loc="left")
    ax1.grid(True, axis="y", which="major", ls=":", lw=0.6, alpha=0.7)
    ax1.legend(loc="upper left", frameon=False, fontsize=6.5)

    ax2.set_ylabel("Cross-edge traffic (MB)")
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=6.3)
    ax2.set_title("(b) Cross-edge traffic", loc="left")
    ax2.grid(True, axis="y", which="major", ls=":", lw=0.6, alpha=0.7)

    fig.tight_layout(w_pad=1.0)
    fig.savefig(out, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    print(f"[plot] wrote {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--scaling-json", type=Path, default=None,
                    help="scaling JSON to plot (default: "
                         "outputs/scaling/scaling_paper.json)")
    ap.add_argument("--fault-json", type=Path,
                    default=Path(__file__).resolve().parents[1]
                    / "outputs" / "fault" / "fault.json")
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    plot_scaling(args.out_dir / "fig_scaling.pdf", args.scaling_json)
    if args.fault_json.exists():
        plot_fault(args.out_dir / "fig_fault.pdf", args.fault_json)
    else:
        print(f"[plot] skip fault figure: {args.fault_json} not found")


if __name__ == "__main__":
    main()
