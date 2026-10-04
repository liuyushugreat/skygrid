"""Structurally different DAG instances (camera-ready addition).

Runs a small, fixed set of configurations -- LDG+static, LDG+COP-H, and
full SkyGrid -- on one or more alternative DAG definitions (see
``configs/dag_*.yaml``) across several seeds, and reports mean/std of
p99 latency and cross-edge traffic.  The point is to check whether the
mechanism ranking observed on the default five-operator DAG carries
over to DAGs with a different shape; the instances are *not* claimed to
model any specific application.

Example::

    python scripts/run_dag_variants.py \
        --configs configs/dag_wide_sym.yaml configs/dag_branching.yaml \
        --seeds 20260928 20260929 20260930 \
        --out outputs/dag_variants/dag_variants.json
"""

from __future__ import annotations

import argparse
import math
import statistics as _st
import sys
from pathlib import Path
from typing import Any

from _common import MODULE_ROOT

sys.path.insert(0, str(MODULE_ROOT))

from skygrid.config import SkyGridConfig
from skygrid.runtime import RuntimeConfig, SkyGridRuntime
from skygrid.utils import dump_json
from skygrid.workload import CityScaleWorkload
from skygrid.workload.dag import TaskDAG


BASELINES: list[dict[str, Any]] = [
    {"label": "ldg+static", "partition": "ldg", "placement": "static", "pipeline": "abp"},
    {"label": "ldg+cop",    "partition": "ldg", "placement": "cop",    "pipeline": "abp"},
    {"label": "skygrid",    "partition": "stp", "placement": "cop",    "pipeline": "abp"},
]


def _agg(xs: list[float]) -> dict[str, float]:
    xs = [x for x in xs if isinstance(x, (int, float)) and not math.isnan(x)]
    if not xs:
        return {"mean": float("nan"), "stdev": 0.0, "n": 0}
    return {
        "mean": _st.fmean(xs),
        "stdev": _st.pstdev(xs) if len(xs) > 1 else 0.0,
        "n": len(xs),
    }


def _run_one(cfg: SkyGridConfig, spec: dict[str, Any]) -> dict:
    cfg.partition.method = spec["partition"]
    cfg.placement.method = spec["placement"]
    cfg.pipeline.method = spec["pipeline"]
    dag = TaskDAG.from_config(cfg.dag)
    w = CityScaleWorkload(
        cfg.workload, dag, seed=cfg.seed,
        cells_per_side=cfg.partition.grid.cells_per_side,
    )
    rt = SkyGridRuntime(cfg, RuntimeConfig(label=spec["label"]))
    return rt.run(w).to_json()


def _dag_signature(cfg: SkyGridConfig) -> dict[str, Any]:
    return {
        "ops": [
            {"name": o.name, "kind": o.kind, "cost_flops": o.cost_flops,
             "state_refs": o.state_refs}
            for o in cfg.dag.ops
        ],
        "edges": [list(e) for e in cfg.dag.edges],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--configs", nargs="+", default=[
        str(MODULE_ROOT / "configs" / "dag_wide_sym.yaml"),
        str(MODULE_ROOT / "configs" / "dag_branching.yaml"),
    ])
    p.add_argument("--seeds", nargs="+", type=int,
                   default=[20260928, 20260929, 20260930])
    p.add_argument("--out", default=None)
    args = p.parse_args()

    out_path = Path(args.out) if args.out else (
        MODULE_ROOT / "outputs" / "dag_variants" / "dag_variants.json"
    )

    results: list[dict[str, Any]] = []
    for cfg_path in args.configs:
        cfg_path = Path(cfg_path)
        name = cfg_path.stem
        per_baseline: dict[str, list[dict]] = {b["label"]: [] for b in BASELINES}
        for seed in args.seeds:
            for spec in BASELINES:
                cfg = SkyGridConfig.load(cfg_path)
                cfg.seed = int(seed)
                m = _run_one(cfg, spec)
                per_baseline[spec["label"]].append(m)
                print(
                    f"[dag-variants] {name:<16} {spec['label']:<11} seed={seed} "
                    f"p99={m['latency_ms']['p99']:.2f}ms "
                    f"xedge={m['cross_edge_bytes']/1e6:.1f}MB "
                    f"tput={m['throughput_ops']:.1f}ops/s",
                    flush=True,
                )
        summary = []
        for label, runs in per_baseline.items():
            summary.append({
                "label": label,
                "n_seeds": len(runs),
                "latency_p50_ms": _agg([r["latency_ms"]["p50"] for r in runs]),
                "latency_p99_ms": _agg([r["latency_ms"]["p99"] for r in runs]),
                "throughput_ops": _agg([r["throughput_ops"] for r in runs]),
                "cross_edge_mb": _agg([r["cross_edge_bytes"] / 1e6 for r in runs]),
                "placement": runs[0]["placement_info"]["assignment"] if runs else {},
            })
        results.append({
            "dag": name,
            "config_path": str(cfg_path),
            "dag_signature": _dag_signature(SkyGridConfig.load(cfg_path)),
            "summary": summary,
            "raw": per_baseline,
        })

    dump_json(out_path, {"seeds": list(args.seeds), "results": results})
    print(f"\n[dag-variants] wrote {out_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
