# SkyGrid

**A Distributed Edge–Cloud Runtime for Hardware-Aware Partitioning and Placement of Hybrid Neural–Symbolic Pipelines**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-%E2%89%A53.10-green.svg)](SkyGrid_spark/pyproject.toml)

This repository is the **open research artifact** accompanying the paper:

> Yushu Liu, Longbiao Wang, Chenglin Du, and Fei Huang.
> *SkyGrid: A Distributed Edge–Cloud Runtime for Hardware-Aware Partitioning and Placement of Hybrid Neural–Symbolic Pipelines.*
> Manuscript under submission.

SkyGrid schedules hybrid neural + symbolic DAGs over an edge–cloud fabric so that city-scale telemetry can approach a ~100 ms p99 SLO while reducing cross-edge traffic and remaining robust under degraded edge capacity.

---

## Overview

A growing class of edge AI workloads runs every event through a **hybrid verification pipeline**: a neural stage scores the event, and a symbolic stage checks it against rules that read the state of spatially neighbouring entities. On modern edge fabrics, one such state reference may cost ~1 μs in unified memory, ~20 μs on RDMA-attached NVMe, or ~12 ms from the cloud—yet many stream/serving runtimes place operators without modelling this hierarchy.

SkyGrid treats **tiered state access** as a first-class signal through three co-designed mechanisms:

| Mechanism | Role |
|---|---|
| **STP** (Spatio-Temporal Partitioning) | Capacity-aware spatial grid with FM-style refinement, bounded by \((1+\gamma)\bar{n}\) |
| **COP-H** (Hardware-aware Operator Placement) | Closed-form cost model over compute, transfer, state-tier latency, and queueing; greedy placement + local swap |
| **ABP** (Asynchronous Batched Pipeline) | Micro-batching with bounded staleness and hysteretic backpressure |

Evaluation uses a **deterministic, CPU-only discrete-event simulator** calibrated to published specifications of a compact edge AI node (NVIDIA DGX Spark class) paired with RDMA-capable NVMe storage, on an urban air mobility (UAM) benchmark (10K–100K entities, 4–16 edge units).

**Representative findings** (see paper for full tables and confidence intervals):

- Cross-edge traffic reduced by **2.3–8.1×**
- p99 latency improved by **26.3±1.9%** vs. static placement
- Under severe edge degradation (one of four edges at 5% nominal compute), capacity-aware partitioning holds p99 near **101 ms**, while a locality-only baseline collapses

---

## Repository Structure

```
skygrid/
├── LICENSE                 # Apache License 2.0
├── CITATION.cff            # Machine-readable citation metadata
├── Makefile                # Top-level install / test / reproduce targets
├── README.md
├── SkyGrid_spark/          # SkyGrid runtime + paper reproduction scripts
│   ├── configs/            # Experiment YAML (default, ablation, scaling, …)
│   ├── scripts/            # Table / ablation / scaling / figure runners
│   ├── skygrid/            # Python package (STP · COP-H · ABP · DES)
│   ├── tests/              # Unit tests (18 cases)
│   └── outputs/            # Reference metrics and figures
└── SparkEdgeSim/           # Edge-unit simulator (DGX Spark + GP Spark model)
    ├── configs/            # Hardware-parameter YAML profiles
    ├── src/dgx_gp_spark_sim/
    ├── examples/           # Includes SkyGrid adapter demo
    └── tests/
```

| Component | Purpose in the paper |
|---|---|
| **SkyGrid_spark** | End-to-end runtime, workloads, partitioners, placers, pipeline, DES, and all reported tables/figures |
| **SparkEdgeSim** | Hardware-parameterized edge-unit model (compute + RDMA/NVMe state tiers) used to ground fabric parameters |

> **Disclaimer.** SparkEdgeSim is a *parameterized research simulator*. It is **not** an official one-to-one replica of NVIDIA DGX Spark or GP Spark hardware. Parameters are derived from publicly available specifications and remain configurable.

---

## Requirements

- Python **≥ 3.10**
- Pure CPU execution for the main paper artifact (no GPU, no network services, no API keys)
- Optional: FastAPI stack for SparkEdgeSim’s REST API demos (see `SparkEdgeSim/pyproject.toml`)

---

## Quick Start: Reproduce Paper Results

```bash
git clone git@github.com:liuyushugreat/skygrid.git
cd skygrid

# Install SkyGrid runtime
cd SkyGrid_spark
python -m pip install -r requirements.txt
python -m pip install -e .

# Main evaluation table
python scripts/run_experiment.py \
  --config configs/default.yaml \
  --output outputs/metrics.json

# Full artifact suite (main, multiseed, ablation, scaling, fault, validation, figures)
make all

# Unit tests — expect: 18 passed
pytest -q
```

From the repository root you can also run:

```bash
make install-skygrid
make reproduce-paper
make test-skygrid
```

### Individual experiment scripts

| Script | Paper role |
|---|---|
| `scripts/run_experiment.py` | Main comparison table |
| `scripts/run_multiseed.py` | Multi-seed aggregate (default seeds `20260928–030`) |
| `scripts/run_ablation.py` | Component ablations (STP / COP-H / ABP / state locality) |
| `scripts/run_scaling.py` | Weak / strong / entity scaling |
| `scripts/run_fault.py` | Edge capacity degradation study |
| `scripts/run_validation.py` | Cost-model validation |
| `scripts/run_pipeline_stress.py` | ABP vs. synchronous under bursty load |
| `scripts/run_placement_stress.py` | State-tier-aware COP-H vs. tier-blind LocAware |
| `scripts/run_dag_variants.py` | Structural DAG variants (`configs/dag_wide_sym.yaml`, `configs/dag_branching.yaml`), Sec. "Other DAG Structures" (`make dag-variants`) |
| `scripts/plot_results.py` | Regenerate figures from JSON metrics |
| `scripts/plot_paper_figs.py` | Camera-ready scaling / degradation figures with embedded TrueType fonts (`make paper-figs`) |

Default seed and fabric parameters are pinned in `SkyGrid_spark/configs/*.yaml` for bit-stable reproduction on a single CPU core. Result files used by the paper are checked in under `SkyGrid_spark/outputs/` (including `outputs/dag_variants/dag_variants.json`).

---

## Optional: SparkEdgeSim

```bash
cd SparkEdgeSim
python -m pip install -e ".[dev]"
pytest -q

# SkyGrid-oriented adapter demonstration
python examples/skygrid_style.py
```

See [`SparkEdgeSim/README.md`](SparkEdgeSim/README.md) for the REST API, CLI, and hardware-parameter reference.

---

## Extending the Runtime

- **New partitioner.** Implement under `skygrid/partition/`, register in `skygrid.partition`, and add a row in `scripts/run_experiment.py`.
- **New placer.** Extend `skygrid/placement/`; the cost model is parameterized by TFLOPS, latency, bandwidth, and jitter.
- **New pipeline.** Implement a `PipelineRunner`-style executor under `skygrid/pipeline/` (ABP and Sync are reference implementations).

---

## Citation

If you use this software or build upon the methods, please cite:

```bibtex
@inproceedings{liu2026skygrid,
  title     = {{SkyGrid}: A Distributed Edge--Cloud Runtime for Hardware-Aware
               Partitioning and Placement of Hybrid Neural--Symbolic Pipelines},
  author    = {Liu, Yushu and Wang, Longbiao and Du, Chenglin and Huang, Fei},
  year      = {2026},
  note      = {Manuscript under submission},
  url       = {https://github.com/liuyushugreat/skygrid}
}
```

A machine-readable record is provided in [`CITATION.cff`](CITATION.cff).

---

## License

This project is licensed under the [Apache License 2.0](LICENSE).

---

## Acknowledgments

Hardware parameters used for calibration are taken from publicly available product specifications. Trademarks (including NVIDIA DGX Spark) remain the property of their respective owners and are used here only for research parameterization.
