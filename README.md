# AfterState: State-Faithful Evaluation of Coding-Agent Recovery

Artifact for FSE 2027 submission 3929. The repository contains experimental specifications, configuration registries, paper aggregate data, figure-generation scripts, numerical checks, and a Python implementation of the recovery protocol.

[Artifact contents](ARTIFACT.md) | [Protocol](docs/PROTOCOL.md) | [Adapters](docs/ADAPTERS.md) | [Data and implementation scope](docs/LIMITATIONS.md)

## Data and implementation

| Component | Contents |
|---|---|
| Paper data | Counts and rounded percentages transcribed from the supplied manuscript; source locations and PDF SHA-256 included |
| State conditions | PRE, REAL, UNDO, REINTRO, WORKTREE, OUTSIDE, and eligible POST |
| Controllers | Native, Retry-1, Reflexion, Self-Refine, Inspect-1/3/6, Read-3 |
| Executable examples | Six controlled fixtures: packages, virtual environments, patches, databases, build caches, and generation |
| Statistics | Paired outcomes, repository-cluster bootstrap, interactions, Holm adjustment, held-out selection |
| Figures | Six groups in PNG/SVG/PDF and a self-contained HTML report |
| Original study materials | The 240-site dataset, original snapshots, 63,408 run records, model outputs, and native framework adapters are not included |

Paper aggregates use the provenance label `transcribed_paper_aggregates`. Fixture demonstrations use `new_controlled_demonstration`; adapter experiments use `new_controlled_experiment`. Unavailable numeric entries are stored as `null`.

## Installation and execution

Requirements: Python 3.10+, Git, and pip. Matplotlib and NumPy are used for figures; pytest is used for tests.

```console
python -m pip install -r requirements.txt
python -m afterstate audit
python -m afterstate figures
python -m pytest -q
python -m afterstate demo --output runs/demo
```

The complete sequence is available through:

```console
python scripts/reproduce.py
```

`--skip-demo` omits fixture certification. The examples use local operations and local wheels; they require no model endpoint, API key or GPU. Dependency installation can require network access.

## Outputs

- [Figure report](reports/figures/index.html)
- [Arithmetic checks](reports/paper-audit.json)
- [Fixture run summary](reports/demo/summary.json)
- [Validation results](reports/VALIDATION.md)

## Paired adapter runs

```console
python -m afterstate run --actions-file examples/claim-only.json --categories patch database --controllers Native Retry-1 Inspect-3 --repeats 1 --configuration scripted-claim-only --output runs/claim-check
python -m afterstate analyze runs/claim-check/runs.jsonl --output runs/claim-check/analysis.json
```

The example uses scripted actions. Model integrations use the [JSON adapter interface](docs/ADAPTERS.md). Registered public-framework versions are configuration metadata; native integrations are not included.

## Directory structure

```text
afterstate/    State storage, protocol, fixtures, controllers, statistics, CLI
configs/       Cohorts, model and framework versions, resource settings
data/paper/    Aggregate JSON/CSV and source metadata
docs/          Protocol, interfaces, analysis, scope, upload procedure
examples/      Scripted adapter examples
schemas/       Site and run-record JSON schemas
scripts/       Execution and packaging commands
tests/         Unit and integration tests
reports/       Figures, numerical checks, execution records
```

The [MIT license](LICENSE) applies to the software. Third-party snapshots, model weights and the manuscript PDF are not distributed. Upload instructions are in [docs/RELEASE.md](docs/RELEASE.md).
