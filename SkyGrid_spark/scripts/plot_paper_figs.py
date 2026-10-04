#!/usr/bin/env python3
"""Regenerate the camera-ready paper figures (scaling, graceful degradation).

Figures are rendered with matplotlib using TrueType (Type 42) fonts so the
resulting PDFs pass IEEE PDF eXpress font checks without a separate
outlining pass.

  python scripts/plot_paper_figs.py --out-dir ../figs

Data sources
------------
* Fig. 3 (scaling): the five-point weak/strong scaling series reported in the
  paper.  The values below are the ones plotted in the submitted figure
  (figs/fig_scaling.drawio).  Note that `outputs/scaling/scaling.json`
  produced by `scripts/run_scaling.py` is a *different* (later) run and does
  not reproduce these exact points; pass `--scaling-json` to plot it instead.
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

# --- Fig. 3 data as plotted in the submitted paper ---------------------------
SCALING_EDGES = [1, 2, 4, 8, 16]
WEAK_NORM_TPUT = [1.0, 2.0, 3.9, 7.7, 15.4]  # normalised to 1-edge run
STRONG_P99_MS = [135.0, 92.0, 72.7, 58.0, 49.0]  # 10K entities fixed
SLO_MS = 100.0


def plot_scaling(out: Path, scaling_json: Path | None) -> None:
    edges, weak, strong = SCALING_EDGES, WEAK_NORM_TPUT, STRONG_P99_MS
    if scaling_json is not None:
        data = json.loads(scaling_json.read_text())
        w = sorted(data["weak"], key=lambda r: r["edges"])
        s = sorted(data["strong"], key=lambda r: r["edges"])
        edges = [r["edges"] for r in w]
        base = w[0]["throughput_ops_s"]
        weak = [r["throughput_ops_s"] / base for r in w]
        strong = [r["p99_ms"] for r in s]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.0, 2.35))

    # (a) weak scaling
    ax1.plot(edges, edges, "--", color=C_GREY, lw=1.1, label="Linear ideal")
    ax1.plot(edges, weak, "-o", color=C_BLUE, ms=4.5, label="SkyGrid")
    for x, y in zip(edges, weak):
        ax1.annotate(f"{y:g}", (x, y), textcoords="offset points",
                     xytext=(-2, 6), ha="right", fontsize=6.8, color=C_BLUE)
    ax1.set_xscale("log", base=2)
    ax1.set_yscale("log", base=2)
    ax1.set_xticks(edges)
    ax1.set_xticklabels([str(e) for e in edges])
    ax1.set_yticks(edges)
    ax1.set_yticklabels([str(e) for e in edges])
    ax1.set_xlabel("Edge units (entities scale proportionally)")
    ax1.set_ylabel("Normalised throughput")
    ax1.set_title("(a) Weak scaling", loc="left")
    ax1.grid(True, which="major", ls=":", lw=0.6, alpha=0.7)
    ax1.legend(loc="upper left", frameon=False)

    # (b) strong scaling
    ax2.axhline(SLO_MS, ls="--", color=C_VERMIL, lw=1.1,
                label=f"{SLO_MS:g} ms SLO")
    ax2.plot(edges, strong, "-s", color=C_GREEN, ms=4.5, label="SkyGrid p99")
    for x, y in zip(edges, strong):
        ax2.annotate(f"{y:g}", (x, y), textcoords="offset points",
                     xytext=(0, 6), ha="center", fontsize=6.8, color=C_GREEN)
    ax2.set_xscale("log", base=2)
    ax2.set_xticks(edges)
    ax2.set_xticklabels([str(e) for e in edges])
    ax2.set_ylim(0, 160)
    ax2.set_xlabel("Edge units (10K entities fixed)")
    ax2.set_ylabel("p99 latency (ms)")
    ax2.set_title("(b) Strong scaling", loc="left")
    ax2.grid(True, which="major", ls=":", lw=0.6, alpha=0.7)
    ax2.legend(loc="upper right", frameon=False)

    fig.tight_layout(w_pad=1.6)
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
                    help="plot outputs/scaling/scaling.json instead of the "
                         "paper's figure values")
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
