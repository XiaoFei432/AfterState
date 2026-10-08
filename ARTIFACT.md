# Artifact contents

## Inputs and provenance

The source document is a 21-page manuscript. Its SHA-256 is stored in `data/paper/source.json`. Original experiment code, site snapshots and linked run records were not supplied.

| Data group | Source | Output |
|---|---|---|
| Paper aggregates | Printed manuscript counts and percentages | JSON, CSV, arithmetic audit, figures |
| Controlled mechanisms | Six fixture operations | Site manifests, state fingerprints, certification records |
| Integration runs | Reference repairs and scripted actions | JSONL continuations and controller traces |

## Execution

`python -m afterstate audit` performs 82 arithmetic checks. `python -m afterstate figures` produces six figure groups and an HTML report. Original Figure 7(b) stratum values and the complete Figure 9(b) controller rates are unavailable as numeric data. Missing entries remain `null`.

`python -m afterstate demo` runs six fixtures, each with five mechanical repetitions and three reference-recovery repetitions. Four fixtures have seven eligible state conditions; two have six. The resulting 40 continuations use reference repairs.

## Resources

- Python 3.10+, Git and pip.
- Matplotlib and NumPy for figures; pytest for tests.
- Temporary storage for copied virtual environments and file snapshots; usage depends on the installed interpreter.
- No GPU or external model endpoint for included examples.
- Paper-declared inference hardware and budgets in `configs/registry.json`.

## Included operations

State reconstruction, state surgery, paired feedback, controller execution, resource accounting, final-state scoring, numerical aggregation and figure generation are implemented. Original study membership, original model outcomes, native checkpoints and complete machine snapshots are not included. Implementation boundaries are listed in `docs/LIMITATIONS.md`.
